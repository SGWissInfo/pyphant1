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

u"""Provides unittest classes FieldContainerTestCase.
"""


import unittest

import scipy
import copy, datetime
from pyphant.quantities import Quantity
from pyphant.core.DataContainer import FieldContainer, SampleContainer
from pyphant.core.PyTablesPersister import (saveField, loadField, saveSample,
                                            loadSample, saveExecutionOrder,
                                            loadExecutionOrders)
import numpy
import tables

class ContainerTestCase(unittest.TestCase):
    def setUp(self):
        self.testData = scipy.array([[0.,1.,2.],[3.,4.,5.],[6.,7.,8.]])
        self.longname = u"Sampled Data"
        self.shortname = u"I\\omega"
        self.unit = Quantity('3.14 m')
        self.attributes = {
            'id': 'dummy id',
            'author': 'dummy author',
            'version': 'dummy version',
            'unit': self.unit
            }
        self.eln = tables.open_file('FieldContainerTestCase.h5','w',
                                   title='Testing the saving and restoring of FieldContainers.')
        self.eln.create_group(self.eln.root,'results')
        self.field = FieldContainer(self.testData,longname=self.longname,
                                    shortname=self.shortname,
                                    unit = self.unit,
                                    attributes = self.attributes
                                    )


    def tearDown(self):
        self.eln.close()
        import os
        os.remove('FieldContainerTestCase.h5')

class FieldContainerTestCase(ContainerTestCase):
    def testSaveRestore(self):
        self.field.creator=u"Klaus"
        self.field.seal()
        self.eln.create_group(self.eln.root,'testSaveRestoreField')
        saveField(self.eln,self.eln.root.testSaveRestoreField,self.field)
        restoredField = loadField(self.eln,self.eln.root.testSaveRestoreField)
        self.assertEqual(restoredField,self.field)

    def testUnicodeFields(self):
        self.field.seal()
        unicodeArray = numpy.array([u'Hallo World!',u'Hallo Wörld!'])
        unicodeField = FieldContainer(unicodeArray,longname=u"blabla",
                                    shortname=self.shortname,
                                    unit = 1,
                                    attributes = self.attributes
                                    )
        unicodeField.seal()
        self.eln.create_group(self.eln.root,'testUnicodeFields')
        saveField(self.eln,self.eln.root.testUnicodeFields,unicodeField)
        restoredField = loadField(self.eln,self.eln.root.testUnicodeFields)
        self.assertEqual(restoredField,unicodeField,
                         "Restored unicode string is %s (%s) but is expected to be %s (%s)." % (restoredField.data,restoredField.data.dtype,unicodeField.data,unicodeField.data.dtype))

class ObjectArrayTestCase(ContainerTestCase):
    def testDateTime(self):
        """Test the correct saving and  restoring of object arrays composed from datetime objects."""
        objectArray = numpy.array([datetime.datetime.now() for i in range(10)])
        objectField = FieldContainer(objectArray,longname=u"timestamp",
                                    shortname='t')
        objectField.seal()
        self.eln.create_group(self.eln.root,'testObjectFields')
        saveField(self.eln,self.eln.root.testObjectFields,objectField)
        restoredField = loadField(self.eln,self.eln.root.testObjectFields)
        for i,j in zip(restoredField.data.tolist(),objectField.data.tolist()):
            self.assertEqual(i,j,'Expected %s but got %s!' % (j,i))

class FieldContainerTestCaseWithError(FieldContainerTestCase):
    def setUp(self):
        super(FieldContainerTestCase,self).setUp()
        self.field.error = numpy.ones(self.field.data.shape,'float')

class FieldContainerTestCaseWithMask(FieldContainerTestCase):
    def setUp(self):
        super(FieldContainerTestCase,self).setUp()
        self.field.mask = self.field.data>3

class SampleContainerTestCase(ContainerTestCase):
    def setUp(self):
        super(SampleContainerTestCase,self).setUp()
        self.independent = FieldContainer(0.3*numpy.linspace(0,1,self.testData.shape[0]),
                                          longname='independent variable',
                                          shortname='x',
                                          unit = Quantity('1 mg'),
                                          attributes = copy.copy(self.attributes).update({'independent':True}))
        self.dependent = FieldContainer(9.81*self.independent.data,
                                        dimensions=[self.independent],
                                        longname='dependent variable',
                                        shortname='f',
                                        unit = Quantity('9.81 nN'),
                                        attributes = copy.copy(self.attributes).update({'independent':False}))
        self.sample = SampleContainer([self.dependent,self.field],longname='Sample',shortname='X',
                                      attributes = copy.copy(self.attributes).update({'isSample':'It seems so.'}))
        self.sample.seal()

    def testSaveRestore(self):
        self.eln.create_group(self.eln.root,'testSaveRestoreSample')
        saveSample(self.eln,self.eln.root.testSaveRestoreSample,self.sample)
        restoredSample = loadSample(self.eln,self.eln.root.testSaveRestoreSample)
        self.assertEqual(restoredSample,self.sample)

class SampleContainerInSampleContainerTestCase(SampleContainerTestCase):
    def setUp(self):
        super(SampleContainerInSampleContainerTestCase,self).setUp()
        sample1 = SampleContainer([self.dependent,self.field],longname='First Sample',shortname='X',
                                      attributes = copy.copy(self.attributes).update({'isSample':'It seems so.'}))
        self.independent2 = FieldContainer(0.3*numpy.linspace(0,1,self.testData.shape[0]*10),
                                          longname='independent variable',
                                          shortname='x',
                                          unit = Quantity('1 mg'),
                                          attributes = copy.copy(self.attributes).update({'independent':True}))
        self.dependent2 = FieldContainer(9.81*self.independent2.data,
                                        dimensions=[self.independent2],
                                        longname='dependent variable',
                                        shortname='f',
                                        unit = Quantity('9.81 nN'),
                                        attributes = copy.copy(self.attributes).update({'independent':False}))

        sample2 = SampleContainer([self.dependent2,self.independent2],longname='Second Sample',shortname='Y',
                                      attributes = copy.copy(self.attributes).update({'sample Nr.': 2}))
        self.sample = SampleContainer([sample1,sample2],longname='SampleContainer with Samples',shortname='(X,Y)',
                                      attributes = copy.copy(self.attributes).update({'isSample':'It seems so.'}))
        self.sample.seal()

class ExecutionOrderTestCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.path = tempfile.mktemp()
        self.orders = [({'sock1' : 'emd5://foo', 'sock2' : 'emd5://bar'}, 'baz'),
                       ({'sockA' : 'emd5://quux', 'sockB' : 'emd5://froz'}, 'pink')]

    def testSaveAndLoad(self):
        h5 = tables.open_file(self.path, mode='w')
        for order in self.orders:
            saveExecutionOrder(h5, order)
        h5.close()

        h5 = tables.open_file(self.path)
        orders = loadExecutionOrders(h5)
        h5.close()
        self.assertEquals(sorted(orders), sorted(self.orders))

if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        unittest.main()
    else:
        suite = unittest.TestLoader().loadTestsFromTestCase(eval(sys.argv[1:][0]))
        unittest.TextTestRunner().run(suite)
