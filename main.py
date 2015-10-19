import argparse
import logging
from lxml import etree
import json
import os
import random
import string
from numpy import average
""""""
class StixAnalytix:
    schema_trees = {} #dict of XSD based etrees in the NAME : TREE format
    input_trees = {} #dict of input file based etrees in th NAME : TREE format
    global_stats = {} #holds statistics for derived tags
    SA_full = {} #Holds all relevant information from the input files including children, attributes, and statistic
    to_string_stats = {} #Ho
    legit_children = {}
    
    """__init__ converts the set of XML Schema files that define STIX into a set of e-trees 
    that we can compare against against input STIX files"""
    def __init__(self):
        #Across each file set up schema tree based off that file
        for filename in os.listdir('xsds'):
            filename = 'xsds/' + filename
            xsd_file = open(filename)
            self.schema_trees.update({ filename : etree.parse(xsd_file)})
            xsd_file.close()        
            if len(self.schema_trees[filename].getroot()) > 0:
                logging.info('Added' + filename + 'as to schema trees')
            else:
                logging.warning('%s is of length %s', str(self.filename), 0)
    
    """Parses args and depending on that, process the information and generate analytics accordingly"""
    def main(self, args):
        if args.log:
            logging.basicConfig(filename='example.log', filemode='w', level=logging.DEBUG)
        logging.debug("Args: %s", args)
        
        #takes input files and makes them into etrees
        for filename in args.files:
            self.input_trees[filename.name] = etree.parse(filename)
            filename.close()
        
        #if additional schema files are given, add them
        if args.xsd:
            for filename in args.xsd:
                xsd_file = open(filename)
                self.schema_trees.update({ filename : etree.parse(xsd_file)})
                xsd_file.close()        
                if len(self.schema_trees.getroot()) > 0:
                    logging.info('Added' + filename + 'as to schema trees')
                else:
                    logging.warning('%s is of length %s', str(self.filename), 0)     

        #For each treeified input file, fill up the SA_Full dict with the relevant information  
        for in_tree_key in self.input_trees.keys():
            self.SA_full[in_tree_key] = self.process_stix_tree(self.input_trees[in_tree_key].getroot())
        #For each treeified input file, generates the stats to be printed out
        for in_tree_key in self.input_trees.keys():
            self.to_string_stats[in_tree_key] = self.get_global_statistics(in_tree_key)
        
        #If the debug flag is raised, use the debug printing method
        if args.debug == True:
            print self.to_string_debug()
        else:
            include_leaves = False
            #If the include leaves flag is raised, make sure that the to_string method includes leaves
            if args.includeleaves:
                include_leaves = True
            print self.to_string(include_leaves)
    
    """Takes a tree derived from a Stix file and begins the process of processing it to generate analytics"""                
    def process_stix_tree(self, it_root):
        info_to_return = {                          
                           'Elements' : 
                            {
                            'used' : {},
                            'unused' : []
                            }
                           }
        
        logging.debug("Input tree root is %s", it_root)
        #for each child, populate the info_to_return dictionary
        for child in it_root:
            #get the element name, such as Stix_Header, if it's the parent of an element we're looking for, note it and dive in
            element_name = self.trim_stix_prefix(child.tag)  #trim {stix} and the trailing 's'
            logging.debug("Top level element is %s", element_name)
            #for each child of Package, dive into the individual
            name = self.trim_stix_prefix(child.tag) 
            info_to_return['Elements']['used'][name] = self.populate_statistics(child, it_root)     
        logging.debug(json.dumps(str(info_to_return)))
        return info_to_return
    
    """Generates the number of possible elements based of the xsd files"""
    def get_total_possible_elements(self):
        child_list = []
        for tree in self.schema_trees.values():
            child_list += tree.getroot().xpath("//xsd:complexType//xsd:element/@name",
                                    namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"})
            child_list += tree.getroot().xpath("//xsd:complexType//xsd:element/@ref",
                                    namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"})
        return len(child_list)
    
    """Generates the number of possible attributes based of the xsd files"""
    def get_total_possible_attributes(self):
        attrib_list = [] 
        for tree in self.schema_trees.values():
            attrib_list += tree.getroot().xpath("//xsd:complexType//xsd:attribute/@name",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"})
            attrib_list += tree.getroot().xpath("//xsd:complexType//xsd:attribute/@ref",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"})
        return len(attrib_list)
    
    """Gets the present subelements of the given child"""
    def populate_present_children(self, name, node):        
        pres_children = [self.trim_stix_prefix(child.tag) for child in node]
        return pres_children
    
    """Sort of holder method for a recuresive lookup of possible childre"""
    def populate_possible_children(self, name, node):
        poss_children = set()
        poss_children.update(self.get_possible_children_recursively(name))
        if name == "Properties":
            poss_children.update(self.get_possible_children_recursively(node.attrib['{http://www.w3.org/2001/XMLSchema-instance}type']))
        return list(poss_children)
    
    """Uses a stack to repeated look up and string together a list of all descendants via a hashmap"""
    def get_possible_children_recursively(self, name):
        name = self.trim_stix_prefix(name) 
        #if a name is not present in the legitimate children hashmap, add it (recursively)
        if name not in self.legit_children.keys():
            self.set_legitimate_children_recursively(name)
        clist = []
        rlist = set()
        #start a stack using the direct children of given node
        if isinstance(self.legit_children[name], set) and self.legit_children[name] != set():
            clist = list(self.legit_children[name].copy())
        #for each child present, pop it off the stack, add any subchildren it may have, and then add it to a list of all legitimate children
        while clist:
            child = clist.pop()
            if child not in self.legit_children.keys():
                self.set_legitimate_children_recursively(child)
            if len(self.legit_children[child]) and child not in rlist:
                clist += self.legit_children[child].copy()
                print name + " : "+ child + " C: " + str(clist) +  " P: " + str(rlist)
            rlist.add(child)
        return rlist
    
    """Method creating a set of hash maps that define the possible children of a given element"""    
    def set_legitimate_children_recursively(self, name):
        children = self.get_legitimate_children(name)
        if name not in self.legit_children.keys():
            logging.info(name + " : " + str(children))
            self.legit_children.update({name : children})
            for child in children:
                self.set_legitimate_children_recursively(child)
        return
    
    """Uses a set of XPATH queries to generate a list of possible direct children from the schema"""
    def get_legitimate_children(self, name_to_check):
        ext_name = ''
        child_list = set()
        bases = set()
        #Tweak the name to better fit looking it up     
        if name_to_check.find('}') > 0:
            name_to_check = name_to_check.split('}', 1)[1]
        ext_name = name_to_check.replace('_', '')
        if not ext_name.find('Type') > 0:
            ext_name += 'Type'
        #Across each XSD file, look for that element to generate child and base lists--which extends children off a wider'base'
        for tree in self.schema_trees.values():
            child_list.update(tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:element/@name",
                                    namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = ext_name))
            child_list.update(tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:element/@ref",
                                    namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = ext_name))
            #If a given element extends another, get the valid subelement of the element being extended
            bases.update(tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:extension/@base",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = ext_name))
            bases.update(tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:element/@type",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = ext_name))
            bases.update(tree.getroot().xpath("//xsd:complexType//xsd:element[@name=$n]/@type",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = name_to_check))
        if not bases == set():
            for base in bases:
                if ':' in base:
                    base = base.split(':', 1)[1]
                for tree in self.schema_trees.values():
                    child_list.update(tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:element/@name",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = base))
        return child_list
    
    """Uses a stack to iterate recursively over the present children starting from the given node"""
    def get_present_children_recursively(self, node):
        clist = []
        for child in node:
            clist += child
        rlist = []
        #for each child present, pop it off the stack, add any subchildren it may have, and then add it to a list of all legitimate children
        while clist:
            child = clist.pop()
            if len(child):
                for gchild in child:
                    clist += gchild
            rlist.append(self.trim_stix_prefix(child.tag))
        return rlist     
    
    """Returns the trimmed version of a given node's attributes"""
    def populate_present_attributes(self, name, node):
        return [self.trim_stix_prefix(attr) for attr in node.attrib]
    
    """Based off the current node, we use a filter to find the possible attributes given a node"""
    def populate_possible_attributes(self, name, node):
        legit_attrib = set()
        if name == "Properties": 
            legit_attrib.update(self.get_legitimate_attributes(node.attrib['{http://www.w3.org/2001/XMLSchema-instance}type']))
        legit_attrib.update(self.get_legitimate_attributes(name))#lists all legitimate children of that tag 
        return list(legit_attrib) 
            
    """Uses a set of XPATH queries to generate a list of possible direct atributes from the schema"""
    def get_legitimate_attributes(self, name_to_check):
        ext_name = ''
        attrib_list = set()
        bases = set()
        #Tweak the name to better fit looking it up     
        if name_to_check.find('}') > 0:
            name_to_check = name_to_check.split('}', 1)[1]
        ext_name = name_to_check.replace('_', '')
        if not ext_name.find('Type') > 0:
            ext_name += 'Type'
        #Across each XSD file, look for that element to generate child and base lists--which extends children off a wider'base'
        for tree in self.schema_trees.values():
            attrib_list.update(tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:attribute/@name",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = ext_name))
            #If a given element extends another, get the valid subelement of the element being extended
            bases.update(tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:extension/@base",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = ext_name))
            bases.update(tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:attribute/@type",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = ext_name))
            bases.update(tree.getroot().xpath("//xsd:complexType//xsd:element[@name=$n]/@type",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = name_to_check))
        if not bases == set():
            for base in bases:
                if ':' in base:
                    base = base.split(':', 1)[1]
                for tree in self.schema_trees.values():
                    attrib_list.update(tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:attribute/@name",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = base))
                    sbases = tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:restriction/@base",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = base)
                    #A certain set of attributes extends an extension of a type, so we need to acount for that here
                    for sbase in sbases:
                        if ':' in sbase:
                            sbase = sbase.split(':', 1)[1]
                        ags = []
                        ags = tree.getroot().xpath("//xsd:complexType[@name=$n]//xsd:attributeGroup/@ref",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = sbase)
                        for ag in ags:
                            if ':' in ag:
                                ag = ag.split(':', 1)[1]
                            attrib_list.update( tree.getroot().xpath("//xsd:attributeGroup[@name=$n]//xsd:attribute/@name",
                                namespaces={"xsd" : "http://www.w3.org/2001/XMLSchema"}, n = ag))
                    
        attrib_list.update(["type"])
        return list(attrib_list)
    
    """Given a node, recursively (and directly) populates the the properties of that node
    and all of its children"""
    def populate_statistics(self, node, pnode):
        name = self.trim_stix_prefix(node.tag) 
        nid = name + str(pnode.index(node)) #gives each child element a unique identifier
        logging.debug("Subelement %s is of type", nid, name)
        #Wireframe for properties of a node to be filled in
        properties = {
                      nid : 
                      {
                       'statistics' : 
                       {
                        'num_attr_pres' : 0,
                        'num_attr_poss' : 0,
                        'attr_ratio' : 0.0,
                        'num_direct_child_pres' : 0,
                        'num_direct_child_poss' : 0,
                        'num_recur_child_pres' : 0,
                        'num_recur_child_poss' : 0,
                        'direct_child_ratio' : 0.0,
                        'recur_child_ratio' : 0.0
                        }
                      }
                     }
        #Populate attribute based information including statistics
        properties[nid].update({ 'attr_pres' : self.populate_present_attributes(name, node)})
        properties[nid].update({ 'attr_poss' : self.populate_possible_attributes(name, node)})
        properties[nid]['statistics'].update({
                                  'num_attr_pres' : len(properties[nid]['attr_pres']),
                                  'num_attr_poss' : len(properties[nid]['attr_poss'])
                                })
        if len(properties[nid]['attr_poss']) > 0:
            properties[nid]['statistics']['attr_ratio'] = len(properties[nid]['attr_pres']) / float(len(properties[nid]['attr_poss']))
        #Populate recursive and direct children based information including statistics
        properties[nid].update({ 'direct_child_pres' : self.populate_present_children(name, node)})
        properties[nid].update({ 'recur_child_pres' : self.get_present_children_recursively(node)})
        properties[nid].update({ 'direct_child_poss' : list(self.get_legitimate_children(name))})
        properties[nid].update({ 'recur_child_poss' : self.populate_possible_children(name, node)})
        if len(properties[nid]['direct_child_poss']) > 0:
            properties[nid]['statistics'].update({
                                                      'num_direct_child_pres' : len(properties[nid]['direct_child_pres']),
                                                      'num_recur_child_pres' : len(properties[nid]['recur_child_pres']),
                                                      'num_direct_child_poss' : len(properties[nid]['direct_child_poss']),
                                                      'num_recur_child_poss' : len(properties[nid]['recur_child_poss'])
                                                    })
            properties[nid]['statistics']['direct_child_ratio'] = len(properties[nid]['direct_child_pres']) / float(len(properties[nid]['direct_child_poss']))
            properties[nid]['statistics']['recur_child_ratio'] = len(properties[nid]['recur_child_pres']) / float(len(properties[nid]['recur_child_poss']))

        #Recursively check subelements for children and attributes 
        for child in node:
            c_nid = self.trim_stix_prefix(child.tag)  + str(node.index(child))
            properties[nid][c_nid] = self.populate_statistics(child, node)          
        logging.info("%s added to return dictionary", name)
        return properties

    """Uses the dict containing information on each file to generate a set of analytics
    on each type of tag present in the file"""
    def get_global_statistics(self, filename):
        self.global_stats.update({ filename : {} })
        #walk the SA_full dict to generate the global stats dict
        self.pull_stats(self.SA_full[filename]['Elements']['used'], filename)
        stats_to_return = {
                            'el_count' : 0,
                            'attr_present' : 0,
                            'child_percent' : 0.0,
                            'attr_percent' : 0.0,
                            'overall_percent' : 0.0,
                            'elements' : {}
                           }
        #Generate the statistics for each element in filename
        for e_key, e_value in self.global_stats[filename].iteritems():
            #wireframe for element's statistics
            stats_to_return['elements'].update({
                                     e_key : 
                                     {
                                      'count' : 0,
                                      'num_direct_child_pres' : 0,
                                      'num_recur_child_pres' : 0,
                                      'num_direct_child_poss' : 0,
                                      'num_recur_child_poss' : 0,
                                      'num_attr_pres' : 0,
                                      'num_attr_poss' : 0,
                                      'attr_ratio' : 0.0,
                                      'direct_child_ratio' : 0.0,
                                      'recur_child_ratio' : 0.0,
                                      'attr_max' : 0,
                                      'child_max' : 0,
                                      'attr_min' : 0,
                                      'child_min' : 0,
                                      'attr_avg' : 0,
                                      'child_avg' : 0,
                                      'attr_list' : [],
                                      'child_list' : []
                                      }
                                    })
            #gets statistics from a node's children and attributes 
            for ce_key, ce_value in e_value.iteritems():
                stats_to_return['el_count'] = stats_to_return['el_count'] + 1
                stats_to_return['attr_present'] += self.global_stats[filename][e_key][ce_key]['num_attr_pres']
                stats_to_return['elements'][e_key]['count'] = stats_to_return['elements'][e_key]['count'] + 1
                stats_to_return['elements'][e_key]['num_attr_pres'] += self.global_stats[filename][e_key][ce_key]['num_attr_pres']
                stats_to_return['elements'][e_key]['attr_list'].append(self.global_stats[filename][e_key][ce_key]['num_attr_pres'])
                stats_to_return['elements'][e_key]['num_attr_poss'] += self.global_stats[filename][e_key][ce_key]['num_attr_poss']
                stats_to_return['elements'][e_key]['num_direct_child_pres'] += self.global_stats[filename][e_key][ce_key]['num_direct_child_pres']
                stats_to_return['elements'][e_key]['num_recur_child_pres'] += self.global_stats[filename][e_key][ce_key]['num_recur_child_pres']
                stats_to_return['elements'][e_key]['child_list'].append(self.global_stats[filename][e_key][ce_key]['num_direct_child_pres'])
                stats_to_return['elements'][e_key]['num_direct_child_poss'] += self.global_stats[filename][e_key][ce_key]['num_direct_child_poss']                
                stats_to_return['elements'][e_key]['num_recur_child_poss'] += self.global_stats[filename][e_key][ce_key]['num_recur_child_poss']  
            #Generate ratios based on the information from previously geerated info 
            if stats_to_return['elements'][e_key]['num_attr_poss'] > 0:
                stats_to_return['elements'][e_key]['attr_ratio'] = (stats_to_return['elements'][e_key]['num_attr_pres'] / float(stats_to_return['elements'][e_key]['num_attr_poss']))*100
            if stats_to_return['elements'][e_key]['num_recur_child_poss'] > 0:
                stats_to_return['elements'][e_key]['recur_child_ratio'] = ((stats_to_return['elements'][e_key]['num_recur_child_pres']) / float(( stats_to_return['elements'][e_key]['num_recur_child_poss'])))*100
            if stats_to_return['elements'][e_key]['num_direct_child_poss'] > 0:
                stats_to_return['elements'][e_key]['direct_child_ratio'] = ((stats_to_return['elements'][e_key]['num_direct_child_pres']) / float(( stats_to_return['elements'][e_key]['num_direct_child_poss'])))*100
            #Generate min, max, and avg of the lists of number of children/attributes
            stats_to_return['elements'][e_key]['attr_max'] = max(stats_to_return['elements'][e_key]['attr_list'])
            stats_to_return['elements'][e_key]['child_max'] = max(stats_to_return['elements'][e_key]['child_list'])
            stats_to_return['elements'][e_key]['attr_min'] = min(stats_to_return['elements'][e_key]['attr_list'])
            stats_to_return['elements'][e_key]['child_min'] = min(stats_to_return['elements'][e_key]['child_list'])
            stats_to_return['elements'][e_key]['attr_avg'] = average(stats_to_return['elements'][e_key]['attr_list'])
            stats_to_return['elements'][e_key]['child_avg'] = average(stats_to_return['elements'][e_key]['child_list'])
        #Get overall statistics for the file
        stats_to_return['attr_percent'] = stats_to_return['attr_present'] / float(self.get_total_possible_attributes())
        stats_to_return['child_percent'] = stats_to_return['el_count'] / float(self.get_total_possible_elements())
        stats_to_return['overall_percent'] = (stats_to_return['el_count'] +  stats_to_return['attr_present']) / float(self.get_total_possible_elements() + self.get_total_possible_attributes())
        logging.info("Statistics have been successfully generated")
        return stats_to_return
    
    """Recursively walks the SA_Full dict and extracts statistics based information based off of it"""   
    def pull_stats(self, node, filename):
        for key, item in node.iteritems():
            if isinstance(item, dict):
                if item.has_key('statistics'):
                    #Strip the identifying # from the end of the element, then use that to generate a (semi) uuid and ad it to stats
                    el_type = key.rstrip('1234567890.')
                    if not self.global_stats[filename].has_key(el_type):
                        self.global_stats[filename].update({ el_type : {} })
                    while self.global_stats[filename][el_type].has_key(key):
                        key += random.choice(string.letters)
                    self.global_stats[filename][el_type].update({ key : item['statistics']})
                self.pull_stats(item, filename)
            else:
                pass
    
    """Simply prints the SA_Full dict, which contains basically all the information on the given input files"""
    def to_string_debug(self):
        to_string = ""
        if len(self.SA_full) > 0:
            for filename in self.SA_full.keys():
                to_string += "\n\n---------------" + filename + "---------------\n"
                to_string += json.dumps(self.SA_full[filename], sort_keys=True, indent=2)
            return to_string
        else:
            return logging.ERROR("SA_full dict is empty--you may need to run process(filename)")
    
    """Prints a 'pretty' version of Stix Analytix for each input file"""
    def to_string(self, include_leaves):
        to_string = "Max Elements:  " + str(self.get_total_possible_elements()) + "\n"
        to_string += "\nMax Atributes: " + str(self.get_total_possible_attributes()) + "\n" 
        if len(self.SA_full) > 0:
            for filename in self.to_string_stats:
                to_string += "\n---------------" + filename + "---------------\n"
                to_string += "STIX Package:"
                to_string += "\n\t# Elements:               " + str(self.to_string_stats[filename]['el_count'])
                to_string += "\n\tElement %:                " + str(self.to_string_stats[filename]['child_percent'])
                to_string += "\n\tAttributes:               " + str(self.to_string_stats[filename]['attr_present'])
                to_string += "\n\tAttribute %:              " + str(self.to_string_stats[filename]['attr_percent'])
                to_string += "\n\tOverall %:                " + str(self.to_string_stats[filename]['overall_percent'])
                for ekey, evalue in self.to_string_stats[filename]['elements'].iteritems():
                    if include_leaves == False and self.to_string_stats[filename]['elements'][ekey]['num_direct_child_pres'] == 0 and self.to_string_stats[filename]['elements'][ekey]['num_attr_pres'] == 0:
                        continue
                    else:
                        to_string += "\n\t" + ekey + ":"
                        to_string += "\n\t\tCount:                " + str(self.to_string_stats[filename]['elements'][ekey]['count'])
                        to_string += "\n\t\tDirect SubElements:   " + str(self.to_string_stats[filename]['elements'][ekey]['num_direct_child_pres'])
                        to_string += "\n\t\tRecur SubElements:    " + str(self.to_string_stats[filename]['elements'][ekey]['num_recur_child_pres'])
                        if self.to_string_stats[filename]['elements'][ekey]['num_direct_child_pres'] > 0:
                            to_string += "\n\t\t\tDirect Element %: " + str(self.to_string_stats[filename]['elements'][ekey]['direct_child_ratio'])
                            to_string += "\n\t\t\tRecur Element %:  " + str(self.to_string_stats[filename]['elements'][ekey]['recur_child_ratio'])
                            to_string += "\n\t\t\tAvg SubElement #: " + str(self.to_string_stats[filename]['elements'][ekey]['child_avg']) 
                            to_string += "\n\t\t\tMin SubElements:  " + str(self.to_string_stats[filename]['elements'][ekey]['child_min']) 
                            to_string += "\n\t\t\tMax SubElements:  " + str(self.to_string_stats[filename]['elements'][ekey]['child_max']) 
                        to_string += "\n\t\tAttributes:           " +  str(self.to_string_stats[filename]['elements'][ekey]['num_attr_pres'])
                        if self.to_string_stats[filename]['elements'][ekey]['num_attr_pres'] > 0:
                            to_string += "\n\t\t\tAttribute %:      " + str(self.to_string_stats[filename]['elements'][ekey]['attr_ratio'])
                            to_string += "\n\t\t\tAvg Attribute #:  " + str(self.to_string_stats[filename]['elements'][ekey]['attr_avg']) 
                            to_string += "\n\t\t\tMin Attributes:   " + str(self.to_string_stats[filename]['elements'][ekey]['attr_min']) 
                            to_string += "\n\t\t\tMax Attributes:   " + str(self.to_string_stats[filename]['elements'][ekey]['attr_max'])
            return to_string 
        else:
            return logging.ERROR("SA_full dict (and therefore the summary dict) is empty--you may need to run process(filename)")
    
    """trim {stix url} and the trailing 's' from str, list, or Element"""
    def trim_stix_prefix(self, to_trim):
        trimmed = to_trim.split('}')[-1]
        if ':' in trimmed:
            trimmed = trimmed.split(':')[-1]
        return trimmed   
        
"""BEGIN CODE"""
#get dictionary with all stix element's and their child elements
stix_report = StixAnalytix()

#sets up argument parsing
parser = argparse.ArgumentParser(description='Run Analytics on a stix file or directory')
parser.add_argument('files', type=file, nargs='+', help='A string representing a file or multiple files')
parser.add_argument('-x', '--xsd', type=argparse.FileType('r'), help="optional flag for additional xsd files to integrate into the schema")
parser.add_argument('-d','--debug', action='store_true', help='Displays the full version of Stix Analytix, as opposed to the normal summary')
parser.add_argument('-l','--log', action='store_true', help='flag for logging to file')
parser.add_argument('-i','--includeleaves', action='store_true', help='flag for logging to file')

#runs the program
stix_report.main(parser.parse_args())



