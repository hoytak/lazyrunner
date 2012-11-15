import logging

__custom_handlers = []

def resetAndInitLogging(opttree):
    global __custom_handlers
    
    logging.basicConfig