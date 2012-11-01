import imp
from os.path import split, join

loaded_modules = {}

def loadModule(d, m = None):
    """
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
        

