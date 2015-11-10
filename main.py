import argparse
import logging
from lxml import etree, objectify
import json
import os
import random
import string
from numpy import average

g_child_lookup = {}
g_schemas = {}

"""Generates the number of possible elements based off the given schemas"""
def get_total_possible_elements(schemas = None):
    global g_schemas
    if not schemas:
        schemas = g_schemas
    children_count = 0
    for schema in schemas.values():
        children_count += len(schema.tree.getroot().xpath("//xsd:complexType//xsd:element/@name",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}))
        children_count += len(schema.tree.getroot().xpath("//xsd:complexType//xsd:element/@ref",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}))
    return children_count

"""Generates the number of possible attributes based off the given schemas"""
def get_total_possible_attributes(schemas = None):
    global g_schemas
    if not schemas:
        schemas = g_schemas
    attrib_count = 0
    for schema in  schemas.values():
        attrib_count += len(schema.tree.getroot().xpath("//xsd:complexType//xsd:attribute/@name",
                            namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}))
        attrib_count += len(schema.tree.getroot().xpath("//xsd:complexType//xsd:attribute/@ref",
                            namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}))
    return attrib_count

"""trim {namespace} from a string"""
def trim_namespace(to_trim):
    if '}' in to_trim:
        return to_trim.split('}')[-1]
    elif ':' in to_trim:
        return to_trim.split(':')[-1]
    else:
        return to_trim
        
"""get the namespace from a string in the {ns}element"""
def get_namespace(to_trim, analytic = None):
    if '}' in to_trim:
        return to_trim.split('}')[0][1:]
    elif ':' in to_trim and analytic is not None:
        return analytic.stix.tree.getroot().nsmap[to_trim.split(':')[0]]
    elif ':' in to_trim:
        return to_trim.split(':')[0]
    else:
        return to_trim
    
""""""
class StixInput:
    def __init__(self, ifile):
        self.filename = ifile.name
        self.tree = etree.parse(ifile)
        logging.info('Generated input etree from' + ifile.name)        
        if not self.check_if_stix(self.tree.getroot()):
            logging.error("Input file" + self.tree.name + "is not a valid stix file")
        self.root = self.tree.getroot()
        
    """Returns true if the file is a valid stix file"""
    def check_if_stix(self, input_root):
        qname = etree.QName(input_root)
        return qname.namespace.startswith("http://stix.mitre.org")
            
class ElementStats:
    def __init__(self, name, nid):
        self.name = name
        self.id = nid
        self.attr_pres = 0
        self.attr_poss = 0
        self.attr_ratio = 0.0
        self.direct_child_pres = 0
        self.direct_child_poss = 0
        self.recur_child_pres = 0
        self.recur_child_poss = 0
        self.direct_child_ratio = 0.0
        self.recur_child_ratio = 0.0
                
class FileStats:
    def __init__(self, filename):
        self.filename = filename
        self.element_stats = []
        self.schema_count = 0
        self.el_count = 0
        self.attr_present = 0
        self.child_percent = 0.0
        self.attr_percent = 0.0
        self.overall_percent = 0.0
        self.type_stats = {}
 
    """Uses the dict containing information on each file to generate a set of analytics
    on each type of tag present in the file"""
    def generate_file_stats(self):     
        self.el_count = len(self.element_stats)
        #Generate the statistics for each element in filename
    
        types = {}
        for el_stat in self.element_stats:
            self.attr_present += el_stat.attr_pres 
            #Generate ratios based on the information from previously geerated info 
            if el_stat.attr_poss > 0:
                el_stat.attr_percent = (el_stat.attr_pres / float(el_stat.attr_poss))*100
            if el_stat.direct_child_poss > 0:
                el_stat.direct_child_ratio = (el_stat.direct_child_pres / float(el_stat.direct_child_poss))*100            
            if el_stat.recur_child_poss > 0:
                el_stat.recur_child_ratio = (el_stat.recur_child_pres / float(el_stat.recur_child_poss))*100        
                        
            el_type = el_stat.name
            if not types.has_key(el_type):
                types[el_type] = {}
            key = str(el_stat.id)
            while types[el_type].has_key(key):
                key += random.choice(string.letters)
            types[el_type][key] = el_stat
    
        for el_type, el_val in types.iteritems():
            #Generate min, max, and avg of the lists of number of children/attributes
            attr_list = []
            child_list = []
            ratio_list = { 
                          'attribs' : [],
                          'd_child' : [],
                          'r_child' : []
                          }
            self.type_stats[el_type] = {
                                        'num_attr_pres': 0,
                                        'num_direct_child_pres' : 0,
                                        'num_recur_child_pres' : 0,
                                        'count' : 0,
                                        'attr_ratio' : 0.0,
                                        'direct_child_ratio' : 0.0,
                                        'recur_child_ratio' : 0.0,
                                        'attr_max' : 0.0,
                                        'child_max' : 0.0,
                                        'attr_min' : 0.0,
                                        'child_min' : 0.0,
                                        'attr_avg' : 0.0,
                                        'child_avg' : 0.0
                                        }
    
            for el_stat in el_val.itervalues():
                self.type_stats[el_type]['count'] = self.type_stats[el_type]['count'] + 1
                self.type_stats[el_type]['num_attr_pres'] += el_stat.attr_pres
                self.type_stats[el_type]['num_direct_child_pres'] += el_stat.direct_child_pres
                self.type_stats[el_type]['num_recur_child_pres'] += el_stat.recur_child_pres
                attr_list.append(el_stat.attr_pres)
                child_list.append(el_stat.direct_child_pres)
                ratio_list['attribs'].append(el_stat.attr_percent)
                ratio_list['d_child'].append(el_stat.direct_child_ratio)
                ratio_list['r_child'].append(el_stat.recur_child_ratio)
            
            self.type_stats[el_type]['attr_ratio'] = average(ratio_list['attribs'])
            self.type_stats[el_type]['direct_child_ratio'] = average(ratio_list['d_child'])
            self.type_stats[el_type]['recur_child_ratio'] = average(ratio_list['r_child'])
            self.type_stats[el_type]['attr_max'] = max(attr_list)
            self.type_stats[el_type]['child_max'] = max(child_list)
            self.type_stats[el_type]['attr_min'] = min(attr_list)
            self.type_stats[el_type]['child_min'] = min(child_list)
            self.type_stats[el_type]['attr_avg'] = average(attr_list)
            self.type_stats[el_type]['child_avg'] = average(child_list)
            
        #Get overall statistics for the file
        self.attr_percent = (self.attr_present / float(get_total_possible_attributes()))*100
        self.child_percent = (self.el_count / float(get_total_possible_elements()))*100
        self.overall_percent = (self.el_count + self.attr_present) / float(get_total_possible_elements() + get_total_possible_attributes())
        logging.info("Statistics have been successfully generated")

class Analytic:
    def __init__(self, stix):
        self.stix = stix
        self.schemas = {}
        self.stats = FileStats(stix.filename)
        self.info = {}#Holds all relevant information from the stixinput files including children, attributes, and statistic
        logging.info('Generated Analytic object')
    
    """Retrieve all the namespaces and schemalocations needed to validate
        `root`.

        Args:
            root: An etree._Element XML document.

        Returns:
            A dictionary mapping namespaces to schemalocations.

        Note: 
            Lifted from stix_validator.py
    """
    def set_schemas(self, schemas_to_check):
        for elem in self.stix.root.iter():
            for ns in elem.nsmap.itervalues():
                if ns not in self.schemas and ns in schemas_to_check:
                    self.schemas[ns] = schemas_to_check[ns]
                    schemas_to_check[ns].is_used = True
        self.stats.schema_count = len(self.schemas)
        return schemas_to_check
                    
    """Starts analytics generation process"""                
    def process_stix_tree(self):
        logging.debug("Input tree root is %s", self.stix.root.tag)
        #for each child, populate the info_to_return dictionary
        self.info = self.walk_stix(self.stix.root)
        self.stats.generate_file_stats()          

    """Given a node, recursively (and directly) populates the the properties of that node
    and all of its children"""
    def walk_stix(self, node, pnode=None):
        name = trim_namespace(node.tag) 
        if pnode is None:
            nid = name
        else:
            nid = name + str(pnode.index(node)) #gives each child element a relatively unique identifier
        stats = ElementStats(name, nid)
        logging.debug("Subelement %s is of type: ", nid, name)
        properties = {}
        #Populate attribute based information including statistics
        properties['attr_pres'] = self.populate_present_attributes(node)
        properties['attr_poss'] = self.populate_possible_attributes(node)
        stats.attr_pres = len(properties['attr_pres'])
        stats.attr_poss = len(properties['attr_poss'])
        if len(properties['attr_poss']) > 0:
            properties['attr_ratio'] = stats.attr_pres / float(stats.attr_poss)
            
        #Populate recursive and direct children based information including statistics
        properties.update({ 'direct_child_pres' : self.populate_present_children(node)})
        properties.update({ 'recur_child_pres' : self.get_present_children_recursively(node)})
        properties.update({ 'recur_child_poss' : self.populate_possible_children(node)})
        properties.update({ 'direct_child_poss' : list(self.get_legitimate_children(node.tag))})

        
        if len(properties['direct_child_poss']) > 0:
            stats.direct_child_pres = len(properties['direct_child_pres'])
            stats.recur_child_pres = len(properties['recur_child_pres'])
            stats.direct_child_poss = len(properties['direct_child_poss'])
            stats.recur_child_poss = len(properties['recur_child_poss'])
            stats.direct_child_ratio = len(properties['direct_child_pres']) / float(len(properties['direct_child_poss']))
            stats.recur_child_ratio = len(properties['recur_child_pres']) / float(len(properties['recur_child_poss']))
            
        self.stats.element_stats.extend([stats])

        #Recursively check subelements for children and attributes 
        for child in node:
            c_nid = trim_namespace(child.tag) + str(node.index(child))
            properties[c_nid] = self.walk_stix(child, node)
        logging.info("%s added to return dictionary", name)
        return properties
    
    """Gets the present subelements of the given child"""
    def populate_present_children(self, node):        
        return [child.tag for child in node]
    
    """Returns the trimmed version of a given node's attributes"""
    def populate_present_attributes(self, node):
        return [attr for attr in node.attrib]
    
    """Sort of holder method for a recursive lookup of possible children"""
    def populate_possible_children(self, node):
        global g_child_lookup
        clist = set()
        if node.tag not in g_child_lookup:
            clist.update(self.get_legitimate_children(node.tag))
        else: 
            clist.update(g_child_lookup[node.tag])
        if '{http://www.w3.org/2001/XMLSchema-instance}type' in node.attrib and node.attrib['{http://www.w3.org/2001/XMLSchema-instance}type'] not in g_child_lookup:
            clist.update(self.get_legitimate_children(node.attrib['{http://www.w3.org/2001/XMLSchema-instance}type']))
        elif '{http://www.w3.org/2001/XMLSchema-instance}type' in node.attrib and node.attrib['{http://www.w3.org/2001/XMLSchema-instance}type'] in g_child_lookup: 
            clist.update(g_child_lookup[node.attrib['{http://www.w3.org/2001/XMLSchema-instance}type']])
        
        rlist = set()
        while clist:
            child = clist.pop()
            if child not in g_child_lookup:
                self.get_legitimate_children(child)
            if len(g_child_lookup[child]) and child not in rlist:
                clist.update(g_child_lookup[child])
            rlist.add(child)
        return list(rlist)
    
    def get_legitimate_children(self, element_name):
        global g_child_lookup
        
        name = trim_namespace(element_name)
        namespace = get_namespace(element_name, self) #converts namespace from XXXXX: format to {XXXXX} format
                
        if element_name in g_child_lookup:
            return g_child_lookup[element_name]
        else:
            g_child_lookup[element_name] = set()
        
        #Find the appropriate schema for this element
        schema = self.set_schema(namespace)
        nsmap = self.update_nsmap(schema)
        el_type = self.get_element_type(schema, nsmap, name)
        
        #Tweak the name for better looking up     
        if len(el_type):
            el_type = el_type.pop()
            el_ns = get_namespace(el_type)
            el_ns = nsmap[el_ns]
            el_type = trim_namespace(el_type)
            if el_ns != namespace and el_ns in self.schemas:
                schema = self.schemas[el_ns]
        else:
            el_type = name        
        
        children = self.get_children_names(schema, nsmap, el_type)
        for child in children:
            c_ns_and_name = '{' + schema.namespace + '}' + child
            g_child_lookup[element_name].update([c_ns_and_name])
        
        self.set_extended_children(element_name, schema, nsmap, el_type)
        return g_child_lookup[element_name]
    
    """Uses a stack to iterate recursively over the present children starting from the given node"""
    def get_present_children_recursively(self, node):
        clist = node.iterdescendants();
        rlist = []
        #for each child present, pop it off the stack, add any subchildren it may have, and then add it to a list of all legitimate children
        for child in clist:
            rlist.append(child.tag)
        return rlist     
    
    """Based off the current node, we use a filter to find the possible attributes given a node"""
    def populate_possible_attributes(self, node):
        legit_attrib = set()
        legit_attrib.update(self.get_legitimate_attributes(node.tag))#lists all legitimate children of that tag 
        if '{http://www.w3.org/2001/XMLSchema-instance}type' in node.attrib:
            legit_attrib.update(self.get_legitimate_attributes(node.attrib['{http://www.w3.org/2001/XMLSchema-instance}type']))
        return list(legit_attrib) 
            
    """Uses a set of XPATH queries to generate a list of possible direct atributes from the schema"""
    def get_legitimate_attributes(self, element_name):
        global g_schemas
        name = trim_namespace(element_name)
        namespace = get_namespace(element_name, self)
        attr_list = set()
        bases = set()
        
        #Find the appropriate schema for this element
        schema = self.set_schema(namespace)
        nsmap = self.update_nsmap(schema)
        el_type = self.get_element_type(schema, nsmap, name)
        #Tweak the name for better looking up     
        if len(el_type):
            el_type = el_type.pop()
            el_ns = get_namespace(el_type)
            el_ns = nsmap[el_ns]
            el_type = trim_namespace(el_type)
            if el_ns != namespace and el_ns in self.schemas:
                schema = self.schemas[el_ns]
        else:
            el_type = name        
                
        attr_list.update(schema.tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:attribute/@name",
                                    namespaces=nsmap, n = el_type))
        attr_list.update(schema.tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:attribute/@ref",
                                    namespaces = nsmap, n = el_type))
        attr_list.update(schema.tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:attributeGroup/@ref",
                                namespaces=nsmap, n = el_type))
        #If a given element extends another, get the valid subelement of the element being extended
        bases.update(schema.tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:extension/@base",
                                namespaces=nsmap, n = el_type))
        bases.update(schema.tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:restriction/@base",
                                namespaces=nsmap, n = el_type))
        if len(bases):
            for base in bases:
                b_ns = get_namespace(base)
                if b_ns in g_schemas:
                    attr_list.update(self.get_legitimate_attibutes(base))
        attr_list.update(['default', 'fixed', 'form', 'id', 'name', 'ref', 'type', 'use'])
        return attr_list
        
    def set_schema(self, namespace):
        global g_schemas
        if namespace in self.schemas:
            return self.schemas[namespace]
        elif namespace in self.stix.tree.getroot().nsmap:
            namespace = self.stix.tree.getroot().nsmap[namespace]
        g_schemas[namespace].is_used = 1;
        self.schemas.update({namespace : g_schemas[namespace]})
        return g_schemas[namespace]
    
    def update_nsmap(self, schema):
        global g_schemas
        for ns in schema.nsmap: #For any namespaces referred to in the schema, find them and add
            if ns in g_schemas:
                self.schemas[ns] = g_schemas[ns]
                g_schemas[ns].is_used = 1
        return schema.nsmap
    
    def get_element_type(self, schema, nsmap, name):
        return schema.tree.getroot().xpath("//xsd:element[@name=$n]/@type", namespaces=nsmap, n = name)
    
    def get_children_names(self, schema, nsmap, etype):
        names = set()
        names.update(schema.tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:element/@name",
                                    namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = etype))
        names.update(schema.tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:element/@ref",
                                    namespaces = nsmap, n = etype))
        return names

    def get_base(self, schema, nsmap, etype):
        #If a given element extends another, get the valid subelement of the element being extended
        return schema.tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:extension/@base",
                                namespaces=nsmap, n = etype)
    
    def set_extended_children(self, element_name, schema, nsmap, el_type):
        extension = self.get_base(schema, nsmap, el_type)
        if not len(extension):
            return
        extension = extension.pop()
        b_ns = get_namespace(extension)
        if b_ns == 'xs':
             return
        if b_ns in nsmap:
            b_ns = nsmap[b_ns]
        schema = self.set_schema(b_ns)
        nsmap = self.update_nsmap(schema)
        children = self.get_children_names(schema, nsmap, el_type)
        for child in children:
            c_ns_and_name = '{' + b_ns + '}' + child
            g_child_lookup[element_name].update([c_ns_and_name])
    
    def get_ref_element(self, ref_string):
        namespace = get_namespace(ref_string)
        name = trim_namespace(ref_string)
        schema = self.set_schema(namespace)
        nsmap = self.update_nsmap(schema)
        return schema.tree.getroot().xpath("//xsd:element[@name=$n]", namespaces = nsmap, n = name).pop()
    
class Schema:
    def __init__(self, sfile):
        self.is_used = 0
        self.tree = etree.parse(sfile)
        self.root = self.tree.getroot()
        self.namespace = self.root.attrib['targetNamespace']
        logging.info('Generated schema etree from' + sfile.name)
        self.nsmap = self.root.nsmap
        self.nsmap.update({"xsd" : "http://www.w3.org/2001/XMLSchema"})
            
class StixAnalytix:
    """__init__ converts the set of XML Schema files that define STIX into a set of e-trees 
    that we can compare against against stixinput STIX files"""
    def __init__(self):
        self.analytics = []# list of Analytics instances
    
    """Parses args and depending on that, process the information and generate analytics accordingly"""
    def main(self, args):
        global g_schemas
        
        if args.log:
            logging.basicConfig(filename="./StixAnalytix.log", filemode='w', level=logging.INFO)
        logging.debug("Args: %s", args)
        
        #takes stixinput files and makes them into etrees
        for filename in args.files:
            self.analytics.append(Analytic(StixInput(filename)))
        
        #Across each file set up schema tree based off that file
        for filename in os.listdir('xsds'):
            sfile = open('xsds/' + filename, 'r')
            self.add_schema(sfile)
            sfile.close()
        #if additional schema files are given, add them
        if args.xsd:
            for sfile in args.xsd:
                self.add_schema(sfile)
        #For each input stix instance, run analytics
        for instance in self.analytics:
            instance.set_schemas(g_schemas)
            instance.process_stix_tree()
        
        #If the debug flag is raised, use the debug printing method
        if args.debug == True:
            print self.to_string_debug()
        else:
            print self.to_string(args.includeleaves)
            
    def add_schema(self, xsd):
        global g_schemas
        schema_to_add = Schema(xsd)
        namespace = schema_to_add.namespace
        if namespace not in g_schemas:
            g_schemas[namespace] = schema_to_add
            logging.info('Added' + xsd.name + 'to schema locations')
        else:
            logging.debug(xsd.name + 'is a duplicate of another XSD using namespace: ' + namespace)
    
    """Simply prints the dict containing the raw info on the STIX file """
    def to_string_debug(self):
        if len(self.analytics) > 0:
            to_string =""
            for analytic in self.analytics:
                to_string += "\n\n---------------" + analytic.stix.filename + "---------------\n"
                to_string += json.dumps(analytic.info, indent=2)
            return to_string
        else:
            return logging.ERROR("SA_full dict is empty--you may need to run process(filename)")
    
    """Prints a 'pretty' version of Stix Analytix for each stixinput file"""
    def to_string(self, include_leaves):
        global g_schemas
        to_string  = "XSDs included:         "  + str(len(g_schemas)) + "\n"
        to_string += "XSDs used:             "  + str(sum([schema.is_used for schema in g_schemas.itervalues()])) + "\n"
        to_string += "Unique XSD Elements:   " + str(get_total_possible_elements()) + "\n"
        to_string += "Unique XSD Attributes: " + str(get_total_possible_attributes()) + "\n" 
        if len(self.analytics) > 0:
            for analytic in self.analytics:
                to_string += "\n---------------" + analytic.stix.filename + "---------------\n"
                to_string += "File:"
                to_string += "\n\t# Schemas:                " + str(analytic.stats.schema_count)
                to_string += "\n\t# Elements:               " + str(analytic.stats.el_count)
                to_string += "\n\tElement %:                " + str(analytic.stats.child_percent)
                to_string += "\n\tAttributes:               " + str(analytic.stats.attr_present)
                to_string += "\n\tAttribute %:              " + str(analytic.stats.attr_percent)
                to_string += "\n\tOverall %:                " + str(analytic.stats.overall_percent)
                for ekey in analytic.stats.type_stats.iterkeys():
                    if include_leaves == False and analytic.stats.type_stats[ekey]['num_direct_child_pres'] == 0 and analytic.stats.type_stats[ekey]['num_attr_pres'] == 0:
                        continue
                    else:
                        to_string += "\n\t" + ekey + ":"
                        to_string += "\n\t\tCount:                " + str(analytic.stats.type_stats[ekey]['count'])
                        to_string += "\n\t\tDirect SubElements:   " + str(analytic.stats.type_stats[ekey]['num_direct_child_pres'])
                        to_string += "\n\t\tRecur SubElements:    " + str(analytic.stats.type_stats[ekey]['num_recur_child_pres'])
                        if analytic.stats.type_stats[ekey]['num_direct_child_pres'] > 0:
                            to_string += "\n\t\t\tDirect Element %: " + str(analytic.stats.type_stats[ekey]['direct_child_ratio'])
                            to_string += "\n\t\t\tRecur Element %:  " + str(analytic.stats.type_stats[ekey]['recur_child_ratio'])
                            to_string += "\n\t\t\tAvg SubElement #: " + str(analytic.stats.type_stats[ekey]['child_avg']) 
                            to_string += "\n\t\t\tMin SubElements:  " + str(analytic.stats.type_stats[ekey]['child_min']) 
                            to_string += "\n\t\t\tMax SubElements:  " + str(analytic.stats.type_stats[ekey]['child_max']) 
                        to_string += "\n\t\tAttributes:           " +  str(analytic.stats.type_stats[ekey]['num_attr_pres'])
                        if analytic.stats.type_stats[ekey]['num_attr_pres'] > 0:
                            to_string += "\n\t\t\tAttribute %:      " + str(analytic.stats.type_stats[ekey]['attr_ratio'])
                            to_string += "\n\t\t\tAvg Attribute #:  " + str(analytic.stats.type_stats[ekey]['attr_avg']) 
                            to_string += "\n\t\t\tMin Attributes:   " + str(analytic.stats.type_stats[ekey]['attr_min']) 
                            to_string += "\n\t\t\tMax Attributes:   " + str(analytic.stats.type_stats[ekey]['attr_max'])
                to_string += "\n"
            return to_string 
        else:
            return logging.ERROR("SA_full dict (and therefore the summary dict) is empty--you may need to run process(filename)")
    

    

"""BEGIN CODE"""
#get dictionary with all stix element's and their child elements
stix_report = StixAnalytix()

#sets up argument parsing
parser = argparse.ArgumentParser(description='Run Analytics on a stix file or directory')
parser.add_argument('files', type=file, nargs='+', help='A string representing a file or multiple files')
parser.add_argument('-x', '--xsd', type=argparse.FileType('r'), help="optional flag for additional xsd files to integrate into the schema")
parser.add_argument('-d','--debug', action='store_true', help='Displays the full version of Stix Analytix, as opposed to the normal summary')
parser.add_argument('-l','--log', action='store_true', help='Flag for logging to stixanlaytix.log')
parser.add_argument('-i','--includeleaves', action='store_true', help='Flag to toggle including Elements with no children')

#runs the program
stix_report.main(parser.parse_args())



