# Copyright (c) 2006-2014, Rectorate of the University of Freiburg
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

import pkg_resources
pkg_resources.require('pyphant')
pkg_resources.require('pyphant.imageprocessing')
pkg_resources.require('tables')

from pyphant.VersionConfig import ptversion
if ptversion[0] == "3":
    from pyphant.core import PyTablesPersisterpt3
else:
    from pyphant.core import PyTablesPersister

if ptversion[0] == "3":
    from pyphant.core.H5FileHandlerpt3 import H5FileHandler
else:
    from pyphant.core.H5FileHandler import H5FileHandler
    
from ImageProcessing.ImageLoaderWorker import ImageLoaderWorker
from pyphant.core.KnowledgeManager import KnowledgeManager
import glob
import optparse
import sys
import tables
import copy


def processArgs(h5):
    argv = sys.argv[1:]
    help = '-h' in argv or '--help' in argv
    args = filter(lambda a: not a in ['-h', '--help'], argv)
    parser = optparse.OptionParser()
    recipe = PyTablesPersister.loadRecipe(h5)
    plugs = recipe.getAllPlugs()
    for p in plugs:
        parser.add_option(
            "", "--%s" % (p.id, ),
            help="Request result of plug %s" % (p.id, ),
            action="append_const", const=p, dest="requestedResults"
            )
    (options, args) = parser.parse_args(filter(lambda o: 'plug' in o, argv))
    if hasattr(options, "requestedResults") and \
            options.requestedResults and len(options.requestedResults) > 0:
        openSockets = sum(
            [recipe.getOpenSocketsForPlug(p) \
                 for p in options.requestedResults],
            []
            )
        parser.values.socketMap = {}

        def optCallback(opt, opt_str, value, parser, socket):
            try:
                parser.values.socketMap[socket.id] = value
            except:
                parser.values.socketMap = {}
                parser.values.socketMap[socket.id] = value

        for s in openSockets:
            parser.add_option(
                "", "--%s" % (s.id, ),
                help="Feed socket %s with data from argument." % (s.id, ),
                action="callback", callback=optCallback,
                nargs=1, type='string',
                callback_args=(s,)
                )
    if help:
        args.append('-h')
    parser.add_option(
        "-n", "--max-orders-per-file",
        help="Maximal number of orders per file",
        type="int", dest="maxOrders"
        )
    (options, args) = parser.parse_args(argv)
    # Order ::= (socketMap, resultPlug)
    return (
        options, args, recipe,
        [(options.socketMap, [p.id for p in options.requestedResults])]
        )


def f2dc(f):
    il = ImageLoaderWorker()
    il.paramFilename.value = f
    res = il.plugLoadImageAsGreyScale.getResult()
    res.seal()
    return res


def globOrder(order, h5):
    km = KnowledgeManager.getInstance()
    sockMap = {}
    for sSpec in order[0].iteritems():
        if sSpec[1].startswith('emd5://'):
            sockMap[sSpec[0]] = [sSpec[1]]
        else:
            ids = []
            for f in glob.iglob(sSpec[1]):
                dc = f2dc(f)
                if h5 != None:
                    PyTablesPersister.saveResult(dc, h5)
                km.registerDataContainer(dc)
                ids.append(dc.id)
            sockMap[sSpec[0]] = ids
    return (sockMap, order[1])


def main():
    km = KnowledgeManager.getInstance()
    sourcefile = sys.argv[1]
    h5 = tables.open_file(sourcefile, 'r+')
    options, args, recipe, orders = processArgs(h5)
    h5.close()
    import os.path
    km.registerURL("file://" + os.path.realpath(sourcefile))
    orderLists = []
    for order in orders:
        order = globOrder(order, None)
        singles = dict(
            [(socket, id_[0]) \
                 for socket, id_ in order[0].iteritems() if len(id_) == 1]
            )
        lists = dict(
            [(socket, id_) \
                 for socket, id_ in order[0].iteritems() if len(id_) > 1]
            )
        lens = [len(l) for l in lists.itervalues()]
        assert max(lens) == min(lens), "Illegal lengths."
        count = lens[0]
        orderList = []
        for i in xrange(count):
            sockMap = copy.deepcopy(singles)
            for s, l in lists.iteritems():
                sockMap[s] = l[i]
            orderList.append((sockMap, order[1]))
        orderLists.append(orderList)
    orders = sum(orderLists, [])
    if options.maxOrders == None:
        count = len(orders)
    else:
        count = options.maxOrders
    i = 0
    orderLists = []
    while i + count < len(orders):
        orderLists.append(orders[i: i + count])
        i += count
    orderLists.append(orders[i:])
    for i, orderList in enumerate(orderLists):
        filename = os.path.basename(sourcefile)[:-3] + '_%i.h5' % (i, )
        with H5FileHandler(filename, 'w') as handler:
            handler.saveRecipe(recipe)
        h5 = tables.open_file(filename, 'r+')
        for o in orderList:
            PyTablesPersister.saveExecutionOrder(h5, o)
            for data in o[0].values():
                dc = km.getDataContainer(data)
                PyTablesPersister.saveResult(dc, h5)
        h5.close()
    #PyTablesPersister.saveExecutionOrder(h5, o)


if __name__ == '__main__':
    main()
