from cPickle import loads, dumps, PicklingError
import h5py
import os, os.path as osp
import cPickle
from bz2 import BZ2File

from treedict import TreeDict
from numpy import ndarray, dtype

def loadResults(opttree, filename):
    """
    Loads a given results file and returns the TreeDict instance
    containing them.
    """

    filename = osp.expanduser(filename)
    
    if opttree.use_hdf5:
        try:
            fg = h5py.File(filename, 'r')
        
            pt = loadTreeDictFromGroup(fg)

            if (pt.treeName() == "__ValueWrapper__"
                and pt.size() == 1
                and "value" in pt):
                    return pt.value
            else:
                return pt
    
        finally:
            
            try:
                fg.close()
            except UnboundLocalError:
                raise IOError("ERROR Loading %s; aborting" % filename)
    else:
        def with_compression(fatal_on_error):
            try:
                f = BZ2File(filename, 'r')
                return cPickle.load(f)
            except IOError:
                if fatal_on_error:
                    raise
                else:
                    return without_compression(True)

        def without_compression(fatal_on_error):
            try:
                return cPickle.load(open(filename, 'rb'))
            except IOError:
                if fatal_on_error:
                    raise
                else:
                    return without_compression(True)
        
        if opttree.cache_compression:
            return with_compression(False)
        else:
            return without_compression(False)
        
            
def saveResults(opttree, filename, obj):
    
    filename = osp.expanduser(filename)

    d, f = osp.split(filename)
    
    if not osp.exists(d):
        os.makedirs(d)

    if opttree.use_hdf5:

        if type(obj) is not TreeDict:
            obj = TreeDict("__ValueWrapper__", value = obj)

        f = h5py.File(filename, 'w')
        saveTreeDictToGroup(f, obj)
        f.close()
    else:
        f = (BZ2File(filename, 'w')
             if   opttree.cache_compression
             else open(filename, 'wb'))
            
        cPickle.dump(obj, f, protocol=-1)
        f.close()

################################################################################
# Functions specific to the hdf5 stuff

def loadTreeDictFromGroup(g):

    n = loadObjectFromGroup(g, "@@name@@")

    p = TreeDict(n)

    for k, ds in g.iteritems():
        k = str(k)
        if not k.startswith("@"):
            p[k] = loadObjectFromGroup(g, k)

    p.freeze()
    
    return p
    

def saveTreeDictToGroup(g, p):
    
    saveObjectToGroup(g, "@@name@@", p.treeName())

    for k, v in p.iteritems():
        saveObjectToGroup(g, k, v)
                
def saveObjectToGroup(g, key, v, force_pickling = False):

    def write_it(key, data, **kwargs):
        if type(data) is str:
            # So stupid.  Gets around bug in h5py
            data = base64.b64encode(data)

        g.create_dataset(key, data, **kwargs)
        

    assert type(key) is str
    
    if not force_pickling and isinstance(v, ndarray) and not isinstance(v, dtype):
        save_v = v
    elif type(v) is TreeDict:
        # This clears out some weak references, which is a bug currently in treedict :-(.
        save_v = dumps(v.copy(), protocol=-1)
    else:
        try:
            save_v = dumps(v, protocol=-1)
        except PicklingError, e:
            print "ERROR: Dumping key '%s': " % key,
            print str(e)
            return

            
    if not force_pickling:
        try:
            try:
                g.create_dataset(key, data=save_v, compression='lzf')
            except TypeError:
                g.create_dataset(key, data=save_v)
                
        except Exception:
            saveObjectToGroup(g, key, v, force_pickling = True)
            
    else:
        try:
            g.create_dataset(key, data=save_v, compression='lzf')
        except TypeError:
            g.create_dataset(key, data=save_v)
        
def loadObjectFromGroup(g, key):
    
    try:
        v = g[key].value
    except Exception, e:
        raise IOError(("Error retrieving treedict from group %s:\n" % g.name)
                          + str(e))

    if type(v) is str:
        v = base64.b64decode(v)
    
    if isinstance(v, basestring):
        return loads(v)
    else:
        return v
    
