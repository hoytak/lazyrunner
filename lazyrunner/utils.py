import imp
from os.path import split, join

loaded_modules = {}

def loadModule(d, m = None):
    """
    Loads a module relative to the base directory base_dir.  `m` can
    be of the form subdir.m_name, or None.  If None, d points to a
    file/directory containing a module
    """

    if m is None:
        d, m = split(d.replace(".py", ""))
        
    elif m.endswith(".py"):
        m = m[:-3]

    elif m.startswith(d):
        d, m = split(m.replace(".py", ""))

    if '.' in m:
        ml = m.split('.')
        d, m = join(d, *ml[:-1]), ml[-1]

    try:
        if (m, d) in loaded_modules:
            return loaded_modules[(m, d)]
            
        m_data = imp.find_module(m, [d])

        if m_data in loaded_modules:
            return loaded_modules[m_data]
        
        module = imp.load_module(m, *m_data)

        loaded_modules[m_data] = module
        loaded_modules[(m,d)] = module

        return module
    
    finally:
        try:
            m_data[0].close()
        except Exception:
            pass
        
def checkType(value,required_type, name = None, error_message = None):

    def raiseError():
        if error_message is None:
            assert name is not None
            if type(required_type) in [list, tuple]:
                err = ("Type of '%s' must be one of %s."
                      % (name, ','.join(str(t) for t in required_type)))
            else:
                err = ("Type of '%s' must be %s."
                       % (name, str(required_type)))
        else:
            err = error_message
            
        raise TypeError(err)

    if type(required_type) in [list, tuple]:
        for t in required_type:
            if isinstance(value, t):
                return
            
        raiseError()
    else:
        if not isinstance(value, required_type):
            raiseError()
        
def checkValue(value,possible_values, name = None, error_message = None):

    if value not in possible_values:
        if error_message is None:
            assert name is not None
            error_message = ("Value of '%s' must be in %s."
                             % (name, ','.join(sorted(str(v) for v in possible_values))))
            
        raise ValueError(error_message)
    
    
