import cPickle, base64, zlib, inspect, os

template = \
"""
from lazyrunner.axisproxy import AxisProxy

save_p = \\
\"\"\"
%(b64pickle)s
\"\"\"

if __name__ == '__main__':

    from matplotlib.pylab import figure, show

    fig = figure()
    a = fig.add_subplot(111)
    
    axis_proxy = AxisProxy()
    axis_proxy._loadFromPickle(save_p)

    axis_proxy.applyHistory(a)

    show()
"""

class CallProxy:
    def __init__(self, name):
        self.name = name

    def __call__(self, *args, **kwargs):
        
        # frame = inspect.getouterframes(inspect.currentframe())[1]
        frame = inspect.currentframe()
        old_frame, filename, line, function, source, junk = inspect.getouterframes(frame)[1]

        header = "%s, %s, %s " % (os.path.split(filename)[1], function, line)

        log_string = (header + ">>>  "
                      + ("\n" + " "*len(header) + ">>>  ").join(s.strip() for s in source))

        # print arg_string
        
        self.args = args
        self.kwargs = kwargs
        self.log_string = log_string
        
class AxisProxy:

    def __init__(self):
        self.__command_list = []

    def __getattr__(self, name):
        cp = CallProxy(name)
        self.__command_list.append(cp)
        return cp

    def _loadFromPickle(self, save_p):
        self.__command_list = cPickle.loads(
            zlib.decompress(base64.decodestring(save_p)))

    def applyHistory(self, axis_object):
        string_count = {}

        for cp in self.__command_list:
            log_string = cp.log_string

            try:
                count = string_count[log_string]
                string_count[log_string] += 1
            except KeyError:
                string_count[log_string] = count = 1

            if count < 5:
                print log_string
            elif count == 5:
                print log_string + "\n<<< More of these surpressed.>>> "
            
            getattr(axis_object, cp.name)(*cp.args, **cp.kwargs)

    def saveAsScript(self, filename, append_suffix = True):
        b64pickle = base64.encodestring(zlib.compress(cPickle.dumps(self.__command_list, protocol = -1)))

        if not filename.endswith('.py'):
            filename += '.py'

        f = open(filename, 'w')
        f.write(template % {'b64pickle' : b64pickle} )
        f.close()

