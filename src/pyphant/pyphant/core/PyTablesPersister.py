# -*- coding: utf-8 -*-

# Copyright (c) 2006-2009, Rectorate of the University of Freiburg
# Copyright (c) 2009, Andreas W. Liehr (liehr@users.sourceforge.net)
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

u"""
This module provides the facilities to persist a Recipe including any
generated data into a PyTables structure or a HDF5 file.
A rudimentary description of the used file-format follows:
.:Attribut
+:group
#:table
*:array

/results/resId
.longname
.shortname
[field|sample]

sample:
.desc = sample.desc [pickled scipy.dtype]
#data(descDict["col_"+name.encode("utf-8")]=Col(dtype=str(desc.fields[name][0]).capitalize()))
#units(unit,name)

field:
*data
*error
.unit = repr(field.unit)
UNLESS field.dimensions==INDEX:
#dimensions(hash, id)
"""


import tables
from tables import StringCol, Col
import sys
from pyphant.core import (CompositeWorker, DataContainer)

# imports needed for eval when loading?
# this should be fixed by passing an appropiate dict to eval
import datetime
from pyphant.quantities import Quantity
from pyphant.quantities import Quantity as PhysicalQuantity

import scipy
import logging
_logger = logging.getLogger("pyphant")

_reservedAttributes = (
    'longname', 'shortname', 'columns', 'creator', 'machine'
    )


class Connection(tables.IsDescription):
    destinationWorker = tables.StringCol(len("worker_" + str(sys.maxint)) + 1)
    destinationSocket = tables.StringCol(64)


##########################################################################
# Saving Part
##########################################################################
def saveExecutionOrder(h5, order):
    if 'executionOrder' in h5.root:
        executionOrderGroup = h5.root.executionOrder
    else:
        executionOrderGroup = h5.create_group('/', 'executionOrder')
    import md5
    m = md5.new()
    m.update(str(sorted(order[0].items())))  # Call 'sorted' to
                                             # normalize representation
                                             # of order[0]
    m.update(str(sorted(order[1])))
    name = "pre_" + m.hexdigest()
    orderGroup = h5.create_group(executionOrderGroup, name)

    class InputDescription(tables.IsDescription):
        socket = StringCol(max(map(len, order[0].keys())))
        data = StringCol(max(map(len, order[0].values())))

    input = h5.create_table(orderGroup, 'input', InputDescription, "Socket Map")
    m = input.row
    for s, d in order[0].iteritems():
        m['socket'] = s
        m['data'] = d
        m.append()
    input.flush()
    orderGroup._v_attrs.resultPlug = order[1]


def saveRecipe(h5, recipe, saveResults=True):
    recipeGroup = h5.create_group("/", "recipe")
    h5.create_group("/", "results")
    h5.set_node_attr(recipeGroup, "Annotations", recipe._annotations)
    workers = recipe.getWorkers()
    for worker in workers:
        saveWorker(h5, recipeGroup, worker, saveResults)


def saveWorker(h5, recipeGroup, worker, saveResults=True):
    workerGroup = h5.create_group(recipeGroup, "worker_" + str(hash(worker)))
    saveBaseAttributes(h5, workerGroup, worker)
    savePlugs(h5, workerGroup, worker, saveResults)
    saveParameters(h5, workerGroup, worker)


def saveParameters(h5, workerGroup, worker):
    paramGroup = h5.create_group(workerGroup, "parameters")
    for (paramName, param) in worker._params.iteritems():
        h5.set_node_attr(paramGroup, paramName, param.value)


def savePlugs(h5, workerGroup, worker, saveResults=True):
    plugs = h5.create_group(workerGroup, "plugs")
    for (plugName, plug) in worker._plugs.iteritems():
        plugGroup = h5.create_group(plugs, plugName)
        if plug.resultIsAvailable() and saveResults:
            resId = saveResult(plug._result, h5)
            h5.set_node_attr(plugGroup, "result", resId)
        connectionTable = h5.create_table(
            plugGroup, 'connections',
            Connection, expectedrows=len(plug._sockets)
            )
        connection = connectionTable.row
        for socket in plug._sockets:
            connection['destinationWorker'] = (
                "worker_" + str(hash(socket.worker))
                )
            connection['destinationSocket'] = socket.name
            connection.append()
        connectionTable.flush()


def saveBaseAttributes(h5, workerGroup, worker):
    h5.set_node_attr(workerGroup, "module", worker.__class__.__module__)
    h5.set_node_attr(workerGroup, "clazz", worker.__class__.__name__)
    h5.set_node_attr(workerGroup, "WorkerAPIVersion", worker.API)
    h5.set_node_attr(workerGroup, "WorkerVersion", worker.VERSION)
    h5.set_node_attr(workerGroup, "WorkerRevision", worker.REVISION)
    h5.set_node_attr(workerGroup, "Annotations", worker._annotations)


def saveResult(result, h5):
    hash, uriType = DataContainer.parseId(result.id)
    resId = u"result_" + hash
    try:
        resultGroup = h5.get_node("/results/" + resId)
    except tables.NoSuchNodeError:
        resultGroup = h5.create_group(
            "/results", resId, result.id.encode("utf-8")
            )
        if uriType == 'field':
            saveField(h5, resultGroup, result)
        elif uriType == 'sample':
            saveSample(h5, resultGroup, result)
        else:
            raise KeyError(
                "Unknown UriType %s in saving result %s." % (
                    uriType, result.id
                    )
                )
    return resId


def saveSample(h5, resultGroup, result):
    h5.set_node_attr(resultGroup, "longname", result.longname.encode("utf-8"))
    h5.set_node_attr(resultGroup, "shortname", result.shortname.encode("utf-8"))
    h5.set_node_attr(resultGroup, "creator", result.creator.encode("utf-8"))
    h5.set_node_attr(resultGroup, "machine", result.machine.encode("utf-8"))
    for key, value in result.attributes.iteritems():
        if key in _reservedAttributes:
            raise ValueError("Attributes should not be named %s, "
                             "but one was in fact called %s!"
                             % (str(_reservedAttributes), key))
        h5.set_node_attr(resultGroup, key, value)
    #Store fields of sample Container and gather list of field IDs
    columns = []
    for column in result.columns:
        columns.append(saveResult(column, h5))
    h5.set_node_attr(resultGroup, "columns", columns)


def saveField(h5, resultGroup, result):
    def dump(inputList):
        def conversion(arg):
            if type(arg) == type(u' '):
                return arg.encode('utf-8')
            else:
                return arg.__repr__()
        if type(inputList) == type([]):
            return map(conversion, inputList)
        else:
            return map(dump, inputList)
    if result.data.dtype.char in ['U', 'O']:
        unicodeData = scipy.array(dump(result.data.tolist()))
        h5.create_array(
            resultGroup, "data", unicodeData, result.longname.encode("utf-8")
            )
    else:
        h5.create_array(
            resultGroup, "data", result.data, result.longname.encode("utf-8")
            )
    for key, value in result.attributes.iteritems():
        h5.set_node_attr(resultGroup.data, key, value)
    h5.set_node_attr(resultGroup, "longname", result.longname.encode("utf-8"))
    h5.set_node_attr(resultGroup, "shortname", result.shortname.encode("utf-8"))
    h5.set_node_attr(resultGroup, "creator", result.creator.encode("utf-8"))
    h5.set_node_attr(resultGroup, "machine", result.machine.encode("utf-8"))

    if result.error != None:
        h5.create_array(resultGroup, "error", result.error,
                       (u"Error of " + result.longname).encode("utf-8"))
    if result.mask != None:
        h5.create_array(resultGroup, "mask", result.mask,
                       (u"Mask of " + result.longname).encode("utf-8"))
    h5.set_node_attr(resultGroup, "unit", repr(result.unit).encode("utf-8"))
    if result.dimensions != DataContainer.INDEX:
        idLen = max([len(dim.id.encode("utf-8")) for dim in result.dimensions])
        dimTable = h5.create_table(
            resultGroup, "dimensions",
            {"hash": StringCol(32), "id": StringCol(idLen)},
            (u"Dimensions of " + result.longname).encode("utf-8"),
            expectedrows=len(result.dimensions)
            )
        for dim in result.dimensions:
            d = dimTable.row
            d["hash"] = dim.hash.encode("utf-8")
            d["id"] = dim.id.encode("utf-8")
            d.append()
            saveResult(dim, h5)
        dimTable.flush()


##########################################################################
# Loading Part
##########################################################################
def instantiateWorker(parent, workerGroup):
    # better pass as dict to eval
    annotations = workerGroup._v_attrs.Annotations
    module = workerGroup._v_attrs.module
    exec "import " + module  # is this save?
    worker = eval(
        module + "." + workerGroup._v_attrs.clazz + "(parent, annotations)"
        )
    return worker


def restoreParamsToWorker(worker, workerGroup):
    try:
        worker.refreshParams()
    except:
        _logger.warning(
            u"Attempted refreshParam failed for %s. Check Parameters!" % (
                worker.name,
                ),
            exc_info=True
            )
    for paramName in workerGroup.parameters._v_attrs._v_attrnamesuser:
        param = getattr(workerGroup.parameters._v_attrs, paramName)
        if type(param) == scipy.ndarray:
            param = unicode(param)
        elif type(param) == scipy.string_:
            param = str(param)
        elif type(param) == scipy.int32:
            param = int(param)
        try:
            worker.getParam(paramName).overrideValue(param)
        except KeyError:
            _logger.warning(
                u'Could not restore "%s" to parameter: "%s"' % (
                    param, paramName
                    )
                )


def restoreParamsToWorkerParentsFirst(worker, worker2group, visited):
    if worker in visited:
        return
    parents = [s.getPlug().worker for s in worker.getSockets() if s.isFull()]
    for parent in parents:
        restoreParamsToWorkerParentsFirst(parent, worker2group, visited)
    restoreParamsToWorker(worker, worker2group[worker])
    visited.add(worker)


def restoreParamsToWorkers(recipeGroup, workers):
    visited = set()
    worker2group = dict([(workers[wg._v_name], wg) for wg in recipeGroup])
    for worker in worker2group:
        restoreParamsToWorkerParentsFirst(worker, worker2group, visited)


def loadRecipe(h5):
    recipeGroup = h5.root.recipe
    try:
        annotations = recipeGroup._v_attrs.Annotations
    except AttributeError:
        annotations = {}
    recipe = CompositeWorker.CompositeWorker(annotations=annotations)
    workers = {}
    createWorkerGraph(recipeGroup, workers, recipe)
    restoreResultsToWorkers(recipeGroup, workers, h5)
    restoreParamsToWorkers(recipeGroup, workers)
    return recipe


def createWorkerGraph(recipeGroup, workers, recipe):
    for workerGroup in recipeGroup:
        workers[workerGroup._v_name] = instantiateWorker(recipe, workerGroup)
    for workerGroup in recipeGroup:
        for plugGroup in workerGroup.plugs:
            plug = workers[workerGroup._v_name].getPlug(plugGroup._v_name)
            for connection in plugGroup.connections.iterrows():
                workers[connection['destinationWorker']].getSocket(
                    connection['destinationSocket']
                    ).insert(plug)


def restoreResultsToWorkers(recipeGroup, workers, h5):
    for workerGroup in recipeGroup:
        for plugGroup in workerGroup.plugs:
            plug = workers[workerGroup._v_name].getPlug(plugGroup._v_name)
            try:
                resId = plugGroup._v_attrs.result
                resNode = h5.get_node("/results/" + resId)
                hash, uriType = DataContainer.parseId(resNode._v_title)
                if uriType == u'field':
                    result = loadField(h5, resNode)
                elif uriType == u'sample':
                    _logger.info("Trying to load sample data...")
                    result = loadSample(h5, resNode)
                    _logger.info("...successfully loaded.")
                else:
                    raise TypeError(
                        "Unknown result uriType in <%s>" % (
                            resNode._v_title,
                            )
                        )
                plug._result = result
            except (AttributeError, tables.NoSuchNodeError), e:
                _logger.info("Exception: " + str(e))


def loadField(h5, resNode):
    longname = unicode(h5.get_node_attr(resNode, "longname"), 'utf-8')
    shortname = unicode(h5.get_node_attr(resNode, "shortname"), 'utf-8')
    try:
        creator = unicode(h5.get_node_attr(resNode, "creator"), 'utf-8')
        machine = unicode(h5.get_node_attr(resNode, "machine"), 'utf-8')
    except:
        from pyphant.core.Helpers import emd52dict
        emd5dict = emd52dict(resNode._v_title)
        creator = emd5dict['creator']
        machine = emd5dict['machine']
    data = scipy.array(resNode.data.read())

    def loads(inputList):
        if type(inputList) == type([]):
            try:
                return map(lambda s: eval(s), inputList)
            except:
                return map(lambda s: unicode(s, 'utf-8'), inputList)
        else:
            return map(loads, inputList)
    if data.dtype.char == 'S':
        data = scipy.array(loads(data.tolist()))
    attributes = {}
    for key in resNode.data._v_attrs._v_attrnamesuser:
        attributes[key] = h5.get_node_attr(resNode.data, key)
    try:
        error = scipy.array(resNode.error.read())
    except tables.NoSuchNodeError:
        error = None
    try:
        mask = scipy.array(resNode.mask.read())
    except tables.NoSuchNodeError:
        mask = None
    unit = eval(unicode(h5.get_node_attr(resNode, "unit"), 'utf-8'))
    try:
        dimTable = resNode.dimensions
        dimensions = [
            loadField(
                h5,
                h5.get_node(
                    "/results/result_" + DataContainer.parseId(row['id'])[0]
                    )
                )
            for row in dimTable.iterrows()
            ]
    except tables.NoSuchNodeError:
        dimensions = DataContainer.INDEX
    result = DataContainer.FieldContainer(data, unit, error, mask,
                                          dimensions, longname, shortname,
                                          attributes)
    result.creator = creator
    result.machine = machine
    result.seal(resNode._v_title)
    return result


def loadSample(h5, resNode):
    result = DataContainer.SampleContainer.__new__(
        DataContainer.SampleContainer
        )
    result.longname = unicode(h5.get_node_attr(resNode, "longname"), 'utf-8')
    result.shortname = unicode(h5.get_node_attr(resNode, "shortname"), 'utf-8')
    result.creator = unicode(h5.get_node_attr(resNode, "creator"), 'utf-8')
    result.machine = unicode(h5.get_node_attr(resNode, "machine"), 'utf-8')
    result.attributes = {}
    for key in resNode._v_attrs._v_attrnamesuser:
        if key not in _reservedAttributes:
            result.attributes[key] = h5.get_node_attr(resNode, key)
    columns = []
    for resId in h5.get_node_attr(resNode, "columns"):
        nodename = "/results/" + resId
        hash, uriType = DataContainer.parseId(
            h5.get_node_attr(nodename, "TITLE")
            )
        if uriType == 'sample':
            loader = loadSample
        elif uriType == 'field':
            loader = loadField
        else:
            raise KeyError(
                "Unknown UriType %s in saving result %s." % (
                    uriType, result.id
                    )
                )
        columns.append(loader(h5, h5.get_node(nodename)))
    result.columns = columns
    result.seal(resNode._v_title)
    return result


def loadExecutionOrders(h5):
    orders = []
    for orderGroup in h5.root.executionOrder:
        socketMapTable = orderGroup.input
        socketMap = dict(
            [(row['socket'], row['data']) for row in socketMapTable.iterrows()]
            )
        resultPlug = orderGroup._v_attrs.resultPlug
        orders.append((socketMap, resultPlug))
    return orders


def pruneResults(h5):
    h5.remove_node("/results", recursive=True)
    h5.create_group("/", "results")
