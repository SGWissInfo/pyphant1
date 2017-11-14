# -*- coding: utf-8 -*-

# Copyright (c) 2006-2010, Rectorate of the University of Freiburg
# Copyright (c) 2009-2010, Andreas W. Liehr (liehr@users.sourceforge.net)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of the Freiburg Materials Research Center,
#   University of Freiburg nor the names of its contributors may be used to
#   endorse or promote products derived from this software without specific
#   prior written permission.
#
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER
# OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""
This module provides the H5FileHandler class.
"""
import tables
from pyphant.core import DataContainer
from pyphant.quantities import Quantity
PhysicalQuantity = Quantity
from pyphant import tables_version_handler
import logging
import os

from pyphant.core import PyTablesPersister
    
from pyphant.core.DataContainer import IndexMarker
from pyphant.core.Helpers import (utf82uc, emd52dict)
_logger = logging.getLogger("pyphant")

im = IndexMarker()
im_id = u"emd5://pyphant/pyphant/0001-01-01_00:00:00.000000/%s.field" \
        % utf82uc(im.hash)
im_summary = {'id': im_id, 'longname': utf82uc(im.longname),
              'shortname': utf82uc(im.shortname), 'hash': utf82uc(im.hash),
              'creator': u'pyphant', 'machine': u'pyphant',
              'date': u'0001-01-01_00:00:00.000000',
              'unit': 1, 'dimensions': [im_id], 'attributes': {}}


class H5FileHandler(object):
    """
    This class is used to handle IO operations on HDF5 files.
    """
    def __init__(self, filename, mode='a'):
        """
        Opens an HDF5 file.
        filename -- path to the file that should be opened
        mode -- mode in which file is opened. Possible values: 'r', 'w', 'a'
                meaning 'read only', 'overwrite' and 'append'.
                'a' is only allowed for files that are valid HDF5 files
                already.
        """
        assert mode in ['r', 'w', 'a']
        exists = os.path.isfile(filename)
        if mode == 'r' and not exists:
            raise IOError("File '%s' does not exist!" % (filename, ))
        self.filename = filename
        self.mode = mode
        if mode == 'w':
            tmphandle = tables_version_handler.open_file(self.filename, 'w')
            tmphandle.close()
            self.mode = 'a'
        self.handle = None

    def __enter__(self):
        assert self.handle is None
        self.handle = tables_version_handler.open_file(self.filename, self.mode)
        return self

    def __exit__(self, type, value, traceback):
        if self.handle is not None:
            self.handle.close()
            self.handle = None

    def getNodeAndTypeFromId(self, dcId):
        """
        Returns a tuple (HDF5 node, uriType) for the given
        DataContainer emd5.
        dcId -- emd5 of the DataContainer
        """
        dcHash, uriType = DataContainer.parseId(dcId)
        try:
            resNode = self.handle.get_node("/results/result_" + dcHash)
        except (AttributeError, tables.NoSuchNodeError):
            raise AttributeError("Container %s not found in file %s."
                                 % (dcId, self.filename))
        if isinstance(uriType, unicode):
            uriType = uriType.encode('utf-8')
        return (resNode, uriType)

    def isIndexMarker(self, dcId):
        """
        returns True iff the underlying HDF5 file contains dcId and
        dcId belongs to an IndexMarker
        """
        resNode, uriType = self.getNodeAndTypeFromId(dcId)
        if uriType == u'field':
            try:
                resNode._g_check_has_child('dimensions')
            except tables.NoSuchNodeError:
                return True
        return False

    def loadDataContainer(self, dcId):
        """
        Loads a DataContainer from the HDF5 file and returns it as a
        DataContainer instance.
        dcId -- emd5 of the DC to be returned
        """
        resNode, uriType = self.getNodeAndTypeFromId(dcId)
        if uriType == 'field':
            result = self.loadField(resNode)
        elif uriType == 'sample':
            result = self.loadSample(resNode)
        else:
            raise TypeError(
                "Unknown result uriType in <%s>" % (resNode._v_title, )
                )
        return result

    def loadField(self, resNode):
        """
        Loads a FieldContainer from the given node and returns it as an
        instance. This method is intended for internal use only.
        resNode -- node at which the FieldContainer is located in the file.
        """
        return PyTablesPersister.loadField(self.handle, resNode)

    def loadSample(self, resNode):
        """
        Loads a SampleContainer from the given node and returns it as an
        instance. This method is intended for internal use only.
        resNode -- node at which the SampleContainer is located in the file.
        """
        return PyTablesPersister.loadSample(self.handle, resNode)

    def loadSummary(self, dcId=None):
        """
        Extracts meta data about a given DataContainer and returns it
        as a dictionary.
        dcId -- emd5 of the DC to summarize. If the emd5 belongs to an
                IndexMarker object, u'IndexMarker' is returned.
                If dcId == None, a dictionary that maps emd5s to summaries
                is returned, where IndexMarker objects are ignored.
        """
        if dcId is None:
            summary = {}
            for group in self.handle.walk_groups(where="/results"):
                currDcId = group._v_attrs.TITLE
                if len(currDcId) > 0:
                    tmp = self.loadSummary(currDcId)
                    if tmp == 'IndexMarker':
                        summary[im_id] = im_summary
                    else:
                        summary[currDcId] = tmp
        elif self.isIndexMarker(dcId):
            return u'IndexMarker'
        else:
            summary = {}
            summary['id'] = dcId
            resNode, uriType = self.getNodeAndTypeFromId(dcId)
            summary['longname'] = utf82uc(self.handle.get_node_attr(resNode,
                                                                  "longname"))
            summary['shortname'] = utf82uc(
                self.handle.get_node_attr(resNode, "shortname")
                )
            summary.update(emd52dict(dcId))
            try:
                summary['machine'] = utf82uc(
                    self.handle.get_node_attr(resNode, "machine")
                    )
                summary['creator'] = utf82uc(
                    self.handle.get_node_attr(resNode, "creator")
                    )
            except:
                pass  # machine, creator set by emd52dict(dcId) before
            attributes = {}
            if uriType == 'field':
                for key in resNode.data._v_attrs._v_attrnamesuser:
                    attributes[key] = self.handle.get_node_attr(
                        resNode.data, key
                        )
                unit = eval(utf82uc(self.handle.get_node_attr(resNode, "unit")))
                summary['unit'] = unit
                dimTable = resNode.dimensions

                def filterIndexMarker(emd5):
                    if self.isIndexMarker(emd5):
                        return im_id
                    else:
                        return emd5
                dimensions = [filterIndexMarker(row['id']) \
                                  for row in dimTable.iterrows()]
                summary['dimensions'] = dimensions
            elif uriType == 'sample':
                for key in resNode._v_attrs._v_attrnamesuser:
                    if key not in PyTablesPersister._reservedAttributes:
                        attributes[key] = self.handle.get_node_attr(resNode, key)
                columns = []
                for resId in self.handle.get_node_attr(resNode, "columns"):
                    nodename = "/results/" + resId
                    columnId = self.handle.get_node_attr(nodename, "TITLE")
                    columns.append(columnId)
                summary['columns'] = columns
            summary['attributes'] = attributes
        return summary

    def loadRecipe(self):
        return PyTablesPersister.loadRecipe(self.handle)

    def saveDataContainer(self, result):
        """
        Saves a given DataContainer instance to the HDF5 file.
        The DataContainer has to be sealed or at least provide a valid
        emd5 in its '.id' attribute.
        A HDF5 group path that points to the location the DC was stored at
        is returned.
        result -- sealed DC instance
        """
        dcHash, uriType = DataContainer.parseId(result.id)
        resId = u"result_" + dcHash
        try:
            resultGroup = self.handle.get_node("/results/" + resId)
        except tables.NoSuchNodeError:
            try:
                resultGroup = self.handle.create_group(
                    "/results", resId, result.id.encode("utf-8")
                    )
            except tables.NoSuchNodeError:
                self.handle.create_group('/', 'results')
                resultGroup = self.handle.create_group(
                    "/results", resId, result.id.encode("utf-8")
                    )
            if uriType == 'field':
                self.saveField(resultGroup, result)
            elif uriType == 'sample':
                self.saveSample(resultGroup, result)
            else:
                raise KeyError(
                    "Unknown UriType %s in saving result %s." % (
                        uriType, result.id
                        )
                    )
        return resId

    def saveSample(self, resultGroup, result):
        """
        Saves a SampleContainer instance to the given node. This method is
        intended for internal use only.
        resultGroup -- node at which the SampleContainer should be saved
                       in the file.
        result -- SampleContainer instance to be saved
        """
        return PyTablesPersister.saveSample(self.handle, resultGroup, result)

    def saveField(self, resultGroup, result):
        """
        Saves a FieldContainer instance to the given node. This method is
        intended for internal use only.
        resultGroup -- node at which the FieldContainer should be saved
                       in the file.
        result -- FieldContainer instance to be saved
        """
        return PyTablesPersister.saveField(self.handle, resultGroup, result)

    def saveRecipe(self, recipe, saveResults=True):
        """
        Saves a recipe

        recipe -- CompositeWorker to be saved
        saveResults -- Whether to save results of the workers
        """
        return PyTablesPersister.saveRecipe(self.handle, recipe, saveResults)
