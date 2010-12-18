from cPickle import loads, dumps
import h5py
import os, os.path as osp

from treedict import TreeDict

from numpy import ndarray, dtype

def loadResults(filename):
    """
    Loads a given results file and returns the TreeDict instance
    containing them.
    """
    try:
        fg = h5py.File(osp.expanduser(filename), 'r')
    
        p = loadTreeDictFromGroup(fg)
        return p

    finally:
        try:
            fg.close()
        except UnboundLocalError:
            raise IOError("ERROR Loading %s; aborting" % filename)
            

def loadTreeDictFromGroup(g):

    n = loadObjectFromGroup(g, "@@name@@")

    p = TreeDict(n)

    for k, ds in g.iteritems():
        if not k.startswith("@"):
            p[k] = loadObjectFromGroup(g, k)

    p.freeze()
    
    return p
    
def saveResults(filename, r):
    
    filename = osp.expanduser(filename)

    d, f = osp.split(filename)
    
    if not osp.exists(d):
        os.makedirs(d)

    f = h5py.File(filename, 'w')
    saveTreeDictToGroup(f, r)
    f.close()


def saveTreeDictToGroup(g, p):
    
    saveObjectToGroup(g, "@@name@@", p.treeName())

    for k, v in p.iteritems():
        saveObjectToGroup(g, k, v)
                
def saveObjectToGroup(g, key, v, force_pickling = False):

    assert type(key) is str
    
    if not force_pickling and isinstance(v, ndarray) and not isinstance(v, dtype):
        save_v = v
    elif type(v) is TreeDict:
        # This clears out some weak references, which is a bug currently in treedict :-(.
        save_v = dumps(v.copy(), protocol=-1)
    else:
        try:
            save_v = dumps(v, protocol=-1)
        except Exception, e:
            print "Dumping key '%s'; ERROR! " % key
            print str(e)

    if not force_pickling :
        try:
            g.create_dataset(key, data=save_v, compression='lzf')
        except Exception:
            saveObjectToGroup(g, key, v, force_pickling = True)
    else:
        g.create_dataset(key, data=save_v, compression='lzf')
        
def loadObjectFromGroup(g, key):
    
    try:
        v = g[key].value
    except Exception, e:
        raise IOError(("Error retrieving treedict from group %s:\n" % g.name)
                          + str(e))
    
    if type(v) is str:
        return loads(v)
    else:
        return v
    
