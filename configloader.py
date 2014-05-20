import yaml

values = {}

def import_file(filename):
    """Update the values object with the contents from a YAML configuration file
    :param string filename: Name of the file to import

    :throws IOError
    :throws yaml.ParserError
    """
    global values
    values = _merge(yaml.load(open(filename, 'r')), values)

def _merge(new_vals, existing_obj):
    if isinstance(new_vals,dict) and isinstance(existing_obj,dict):
        for k,v in existing_obj.iteritems():
            if k not in new_vals:
                new_vals[k] = v
            else:
                new_vals[k] = _merge(new_vals[k],v)
    return new_vals
