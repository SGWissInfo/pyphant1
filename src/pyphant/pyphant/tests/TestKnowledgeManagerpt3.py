# -*- coding: utf-8 -*-

# Copyright (c) 2006-2008, Rectorate of the University of Freiburg
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

u"""Provides unittest classes
"""


import unittest
from pyphant.core.KnowledgeManager import (KnowledgeManager,
                                           CACHE_MAX_SIZE,
                                           CACHE_MAX_NUMBER)
import pyphant.core.PyTablesPersister as ptp
from pyphant.core.DataContainer import (FieldContainer, SampleContainer)
import numpy as N
import tables
import urllib
import tempfile
import os
import logging
from time import time
import random


class KnowledgeManagerTestCase(unittest.TestCase):
    def setUp(self):
        a = N.array([0, 1, 2, 3])
        self._fc = FieldContainer(a)
        self._fc.seal()

    def testGetLocalFile(self):
        h5fileid, h5name = tempfile.mkstemp(suffix='.h5',prefix='test-')
        os.close(h5fileid)
        h5 = tables.open_file(h5name,'w')
        resultsGroup = h5.create_group("/", "results")
        ptp.saveResult(self._fc, h5)
        h5.close()
        km = KnowledgeManager.getInstance()
        from urllib import pathname2url
        url = pathname2url(h5name)
        if not url.startswith('///'):
            url = '//' + url
        url = 'file:' + url
        km.registerURL(url, temporary=True)
        km_fc = km.getDataContainer(self._fc.id)
        self.assertEqual(self._fc, km_fc)
        os.remove(h5name)

    def testGetHTTPFile(self):
        host = "pyphant.sourceforge.net"
        remote_dir = ""
        url = "http://" + host + remote_dir + "/knowledgemanager-http-test.h5"
        # Get remote file and load DataContainer
        filename, headers = urllib.urlretrieve(url)
        h5 = tables.open_file(filename, 'r')
        for g in h5.walk_groups("/results"):
            if (len(g._v_attrs.TITLE)>0) \
                    and (r"\Psi" in g._v_attrs.shortname):
                http_fc = ptp.loadField(h5,g)
        h5.close()
        km = KnowledgeManager.getInstance()
        km.registerURL(url, temporary=True)
        km_fc = km.getDataContainer(http_fc.id)
        self.assertEqual(http_fc, km_fc)
        os.remove(filename)

    def testGetDataContainer(self):
        km = KnowledgeManager.getInstance()
        km.registerDataContainer(self._fc, temporary=True)
        km_fc = km.getDataContainer(self._fc.id)
        self.assertEqual(self._fc, km_fc)

    def testSCwithSCColumn(self):
        fc_child1 = FieldContainer(longname='fc_child1', data=N.ones((10, 10)))
        fc_child2 = FieldContainer(longname='fc_child2', data=N.ones((20, 20)))
        sc_child = SampleContainer(longname='sc_child', columns=[fc_child1])
        sc_parent = SampleContainer(longname='sc_parent', columns=[sc_child,
                                                                   fc_child2])
        sc_parent.seal()
        km = KnowledgeManager.getInstance()
        km.registerDataContainer(sc_parent, temporary=True)
        lnlist = km.search(['longname'], {'col_of':{'longname':'sc_parent'}})
        lnlist = [entry[0] for entry in lnlist]
        assert len(lnlist) == 2
        assert 'fc_child2' in lnlist
        assert 'sc_child' in lnlist

    def testExceptions(self):
        km = KnowledgeManager.getInstance()
        #TODO:
        #invalid id
        #DataContainer not sealed
        #Local file not readable
        #Register empty hdf

    def testRegisterFMF(self):
        km = KnowledgeManager.getInstance()
        fileid, filename = tempfile.mkstemp(suffix='.fmf', prefix='test-')
        os.close(fileid)
        handler = open(filename, 'w')
        fmfstring = """; -*- fmf-version: 1.0 -*-
[*reference]
title: Knowledge Manager FMF Test
creator: Alexander Held
created: 2009-05-25 08:45:00+02:00
place: Uni Freiburg
[*data definitions]
voltage: V [V]
current: I(V) [A]
[*data]
1.0\t0.5
2.0\t1.0
3.0\t1.5
"""
        handler.write(fmfstring)
        handler.close()
        dc_id = km.registerFMF(filename, temporary=True)
        os.remove(filename)
        km.getDataContainer(dc_id)

    def testCache(self):
        print "Preparing FCs for cache test (cache size: %d MB)..."\
              % (CACHE_MAX_SIZE / 1024 / 1024)
        km = KnowledgeManager.getInstance()
        sizes = [(20, ), (10, 10, 10), (200, 200), (700, 700), (2000, 2000)]
        byte_sizes = [reduce(lambda x, y:x * y, size) * 8 for size in sizes]
        ids = []
        rand_id_pool = []
        assert_dict = {}
        for num in xrange(2 * 20):
            fc = FieldContainer(N.ones((500, 500)))
            fc.data.flat[0] = num
            fc.seal()
            km.registerDataContainer(fc, temporary=True)
            rand_id_pool.append(fc.id)
            assert_dict[fc.id] = num
        for size in sizes:
            fc = FieldContainer(N.ones(size))
            fc.seal()
            km.registerDataContainer(fc, temporary=True)
            ids.append(fc.id)
        for id, bytes in zip(ids, byte_sizes):
            uc_acc_time = 0.0
            c_acc_time = 0.0
            reps = 30
            for rep in xrange(reps):
                t1 = time()
                km.getDataContainer(id, use_cache=False)
                t2 = time()
                uc_acc_time += t2 - t1
            km._cache = []
            km._cache_size = 0
            for rep in xrange(reps):
                t1 = time()
                km.getDataContainer(id)
                t2 = time()
                c_acc_time += t2 - t1
            uc_avr = 1000.0 * uc_acc_time / reps
            c_avr = 1000.0 * c_acc_time / reps
            print "Avr. access time for %0.2f kB sequential read: "\
                  "%0.3f ms unchached, %0.3f ms cached" % (float(bytes) / 1024,
                                                           uc_avr, c_avr)
        km._cache = []
        km._cache_size = 0
        rand_ids = []
        reps = 500
        import pyphant.core.KnowledgeManager
        pyphant.core.KnowledgeManager.CACHE_MAX_NUMBER = 20
        for run in xrange(reps):
            rand_ids.append(rand_id_pool[
                random.randint(0, len(rand_id_pool) - 1)])
        uc_acc_time = 0.0
        c_acc_time = 0.0
        for id in rand_ids:
            t1 = time()
            fc = km.getDataContainer(id, use_cache=False)
            t2 = time()
            uc_acc_time += t2 - t1
        for id in rand_ids:
            t1 = time()
            fc = km.getDataContainer(id)
            t2 = time()
            c_acc_time += t2 - t1
            assert km._cache_size >= 0
            assert km._cache_size <= CACHE_MAX_SIZE
            assert len(km._cache) <= CACHE_MAX_NUMBER
            assert assert_dict[id] == fc.data.flat[0]
        uc_avr = 1000.0 * uc_acc_time / reps
        c_avr = 1000.0 * c_acc_time / reps
        bytes = float(500 * 500 * 8) / 1024
        print "Avr. access time for %0.2f kB random read: "\
              "%0.3f ms unchached, %0.3f ms cached" % (bytes, uc_avr, c_avr)
        print "------ End Cache Test ------"


if __name__ == "__main__":
    import sys
    logger = logging.getLogger('pyphant')
    hdlr = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter('[%(name)s|%(levelname)s] %(message)s')
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(logging.DEBUG)
    if len(sys.argv) == 1:
        unittest.main()
    else:
        suite = unittest.TestLoader().loadTestsFromTestCase(
            eval(sys.argv[1:][0]))
        unittest.TextTestRunner().run(suite)
