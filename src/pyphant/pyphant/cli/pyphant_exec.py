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

import pkg_resources
pkg_resources.require("pyphant")
pkg_resources.require("tables")


def main():
    import sys
    filename = sys.argv[1]
    from pyphant.core import KnowledgeManager
    km = KnowledgeManager.KnowledgeManager.getInstance()
    import os.path
    km.registerURL("file://" + os.path.realpath(filename))
    import tables
    h5 = tables.open_file(filename, 'r+')

    from pyphant.VersionConfig import ptversion
    if ptversion[0] == "3":
        from pyphant.core import PyTablesPersisterpt3
    else:
        from pyphant.core import PyTablesPersister
        
    recipe = PyTablesPersister.loadRecipe(h5)
    executionOrders = PyTablesPersister.loadExecutionOrders(h5)
    h5.close()
    from pyphant.core.Emd5Src import Emd5Src
    for order in executionOrders:
        for socket, emd5 in order[0].iteritems():
            sSpec = socket.split('.')
            w = recipe.getWorker(sSpec[0])
            s = getattr(w, sSpec[-1])
            src = Emd5Src(recipe)
            src.paramEmd5.value = emd5
            if s.isFull():
                s.pullPlug()
            s.insert(src.plugGetDataContainer)
        pSpec = order[1][0].split('.')
        d = recipe.getWorker(pSpec[0])
        plug = getattr(d, pSpec[1])
        res = plug.getResult()
        res.seal()
        h5 = tables.open_file(filename, 'r+')
        PyTablesPersister.saveResult(res, h5)
        h5.close()


if __name__ == '__main__':
    main()
