import tables
ptversion = tables.__version__


def open_file(*args):
    if ptversion[0] == "3":
        return tables.open_file(*args)
    else:
        return tables.openFile(*args) 

def get_node(*args):
    if ptversion[0] == "3":
        return tables.File.get_node(*args)
    else:
        return tables.File.getNode(*args)

def get_node_attr(*args):
    if ptversion[0] == "3":
        return tables.File.get_node_attr(*args)
    else:
        return tables.File.getNodeAttr(*args)
    
def set_node_attr(*args):
    if ptversion[0] == "3":
        return tables.File.set_node_attr(*args)
    else:
        return tables.File.setNodeAttr(*args)

def remove_node(*args):
    if ptversion[0] == "3":
        return tables.File.remove_node(*args)
    else:
        return tables.File.removeNode(*args)
    
def create_table(*args):
    if ptversion[0] == "3":
        return tables.File.create_table(*args)
    else:
        return tables.File.createTable(*args)

def create_array(*args):
    if ptversion[0] == "3":
        return tables.File.create_array(*args)
    else:
        return tables.File.createArray(*args)

def walk_groups(*args):
    if ptversion[0] == "3":
        return tables.File.walk_groups(*args)
    else:
        return tables.File.walkGroups(*args)
    
def create_group(*args):
    if ptversion[0] == "3":
        return tables.File.create_group(*args)
    else:
        return tables.File.createGroup(*args)
    
def _g_check_has_child(*args):
    if ptversion[0] == "3":
        return tables.Group._g_check_has_child(*args)
    else:
        return tables.Group._g_checkHasChild(*args)
