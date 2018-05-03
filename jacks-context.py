#!/usr/bin/env python

# Copyright (c) 2014  Barnstormer Softworks, Ltd.

import multiprocessing as MP
from argparse import ArgumentParser
import time
import json
import sys
import os
import tempfile

import geni.aggregate
from geni.aggregate.frameworks import KeyDecryptionError
from geni.rspec.pgad import Advertisement
import geni.util

extra = {}
advanced_types = []
advanced_hardware = []
advanced_images = []
advanced_link_types = []
aggregates = {
  'names': {},
  'types': {}
}
nomac_images = {}
no_link = {}
stitchable_ig = []
stitchable_eg = []
link_info = {
  'local': [],
  'tunnel': [],
  'stitch-ig': [],
  'stitch-eg': []
}
site_info = {}
I2Switches = {}
debug = False

# --------------------------------------------------
# Load the user's context, which includes their certificate
# and private key.

try:
    # Determine whether the key is passphrase protected
    # based on the exception thrown.
    context = geni.util.loadContext(key_passphrase='NotThePassword')
except TypeError:
    # Key has no passphrase, just load it
    context = geni.util.loadContext()
except KeyDecryptionError:
    # Passphrase protected key, prompt for passphrase
    context = geni.util.loadContext(key_passphrase=True)

##########################################################################


class ConstraintPair:
    def __init__(self):
        self.aCount = {}
        self.bCount = {}
        self.comboCount = {}
        self.aSeen = {}
        self.bSeen = {}
        self.comboSeen = {}

    # Reset seen markers because there is a new node
    def newNode(self):
        self.aSeen = {}
        self.bSeen = {}
        self.comboSeen = {}

    # Mark a combination as being available on this node
    def addPair(self, a, b):
        # Add a to the count if it hasn't been seen
        if a not in self.aSeen:
            if a not in self.aCount:
                self.aCount[a] = 0
            self.aCount[a] += 1
            self.aSeen[a] = 1
        # Add b to the count if it hasn't been seen
        if b not in self.bSeen:
            if b not in self.bCount:
                self.bCount[b] = 0
            self.bCount[b] += 1
            self.bSeen[b] = 1
        # Add the pair (a, b) to the count if it hasn't been seen
        if a not in self.comboCount:
            self.comboCount[a] = {}
        if a not in self.comboSeen:
            self.comboSeen[a] = {}
        if b not in self.comboSeen[a]:
            if b not in self.comboCount[a]:
                self.comboCount[a][b] = 0
            self.comboCount[a][b] += 1
            self.comboSeen[a][b] = 1

    def getPairs(self, is_basic):
        result = []
        for a, bMap in self.comboCount.iteritems():
            for b, count in bMap.iteritems():
                if False and is_basic:
                    # Return pairs with the same node counts as the individuals
                    if count == self.aCount[a] and count == self.bCount[b]:
                        result.append((a, b))
                else:
                    # Return all possible pairs
                    result.append((a, b))
        return result


def calculate_constraints(is_basic, ads, aggregateNames):
    result = []
    result.extend(calculate_type_image(is_basic, ads))
    result.extend(calculate_type_hardware(is_basic, ads))
    calculate_stitching_constraints(is_basic,ads)
    result.extend(calculate_type_link(is_basic, ads, aggregateNames))
    return result



def get_image_id(image, cmurn):
    # imageId = image.url
    # if imageId is None:
    #  imageId = image.name
    imageId = image.name
    if cmurn in aggregates['types'] and aggregates['types'][cmurn] == 'ig':
        urn = imageId
        baseId = urn.split('+')[-1]
        imageId = 'urn:publicid:IDN+emulab.net+image+' + baseId
    return imageId

def calculate_stitching_constraints(is_basic,ads):
    for ad in ads:
        stitch_info = ad.stitchinfo
	if(stitch_info is not None):
	 try:
       		agginfos = stitch_info.aggregates
		for urn,agginfo in agginfos.iteritems():
		  for aggNode in agginfo.nodes:
		  	for aggPort in aggNode.ports:
			  for aggLink in aggPort.links:
			   I2Con = aggLink.al2sinfo
			   if(I2Con is not None):
		 		I2Con = ':'.join(I2Con)
				if(I2Con in I2Switches.keys()):
				  if(urn.startswith("urn:publicid:IDN+exogeni.net:") and urn.endswith("Net+authority+am")):
					urn = urn.replace("Net","vmsite")
				  if(urn not in I2Switches[I2Con]):
			  		(I2Switches[I2Con]).append(urn)
					add_site_I2Connector(urn, I2Con)
				else:
					I2Switches[I2Con] = [urn]
					add_site_I2Connector(urn, I2Con)
	 except Exception as e:
		print "Exception for "+urn+" happened "+str(e)
		continue
    return


def calculate_type_image(is_basic, ads):
    pairMap = {}
    result = []
    for ad in ads:
        for node in ad.nodes:
            cmurn = node.component_manager_id
            if cmurn in pairMap:
                pair = pairMap[cmurn]
            else:
                pair = ConstraintPair()
                pairMap[cmurn] = pair
            pair.newNode()
            slivernames = []
            for name in node.sliver_types:
                if name not in advanced_types:
                    pair.addPair(name, '!')
            for sliver_name, images in node.images.iteritems():
                add_site_type(cmurn, sliver_name)
                for image in images:
                    imageId = get_image_id(image, cmurn)
                    if not is_basic or (sliver_name not in advanced_types and
                                        imageId not in advanced_images):
                        pair.addPair(sliver_name, imageId)
    for cmurn, pair in pairMap.iteritems():
        for sliver_name, image_name in pair.getPairs(is_basic):
            result.append({
             'node': {
               'types': [sliver_name],
               'images': [image_name],
               'aggregates': [cmurn]
             }
            })
    return result


def calculate_type_hardware(is_basic, ads):
    pairMap = {}
    result = []
    for ad in ads:
        for node in ad.nodes:
            cmurn = node.component_manager_id
            if cmurn in pairMap:
                pair = pairMap[cmurn]
            else:
                pair = ConstraintPair()
                pairMap[cmurn] = pair
            pair.newNode()

            slivernames = []
            for name in node.sliver_types:
                if name not in advanced_types:
                    pair.addPair(name, '!')

            hardwarenames = []
            for name, slots in node.hardware_types.iteritems():
                if name not in advanced_hardware:
                    pair.addPair('!', name)

            for hardware_name, slots in node.hardware_types.iteritems():
                add_site_hardware(cmurn, hardware_name)
                for sliver_name in node.sliver_types:
                    if (not is_basic or
                        (sliver_name not in advanced_types and
                         hardware_name not in advanced_hardware)):
                        pair.addPair(sliver_name, hardware_name)
    for cmurn, pair in pairMap.iteritems():
        for sliver_name, hardware_name in pair.getPairs(is_basic):
            result.append({
              'node': {
                'types': [sliver_name],
                'hardware': [hardware_name],
                'aggregates': [cmurn]
              }
            })
    return result


def add_site_type(urn, name):
    site = add_site(urn)
    site['types'][name] = True


def add_site_hardware(urn, name):
    site = add_site(urn)
    site['hardware'][name] = True

def add_site_I2Connector(urn, name):
    site = add_site(urn)
    site['I2Connector'] = name



def add_site(urn):
    if urn not in site_info:
        site_info[urn] = {'types': {}, 'hardware': {}}
    return site_info[urn]


def calculate_type_link(is_basic, ads, aggregateNames):
    result = []
    if len(link_info['stitch-ig']) > 0:
        add_stitchable_constraints(stitchable_ig,
                                   link_info['stitch-ig'], result)
    if len(link_info['stitch-eg']) > 0:
        add_stitchable_constraints(stitchable_eg,
                                   link_info['stitch-eg'], result)
    if len(link_info['tunnel']) > 0:
        tunnelOk = []
        for urn in aggregateNames:
            if (urn in aggregates['types'] and
                    aggregates['types'][urn] == 'ig' and
                    urn not in no_link):
                tunnelOk.append(urn)
        if len(tunnelOk) > 0:
            result.append({
              'node': {'aggregates': tunnelOk},
              'link': {'linkTypes': link_info['tunnel']},
              'node2': {'aggregates': tunnelOk}
            })
    if len(link_info['local']) > 0:
        for urn in aggregateNames:
            if urn not in no_link:
                result.append({
                  'node': {'aggregates': [urn]},
                  'link': {'linkTypes': link_info['local']},
                  'node2': {'aggregates': [urn]}
                })

    return result


def add_stitchable_constraints(list, linkType, result):
    to_exclude = []
    for urn in list:
	try:
		to_exclude = I2Switches[site_info[urn]['I2Connector']]
	except KeyError as e:
		to_exclude = [urn]
        others = find_not(list,to_exclude)
        if len(others) > 0:
            result.append({
              'node': {
                'aggregates': [urn]
              },
              'link': {
                'linkTypes': linkType
              },
              'node2': {
                'aggregates': others
              }
            })


def find_not(list, without):
    result = []
    for item in list:
        if item not in without:
            result.append(item)
    return result

##########################################################################


def calculate_canvas(is_basic, ads, aggregateNames):
    result = {
      'defaults': [],
      'icons': [],
      'types': [],
      'images': [],
      'hardware': [],
      'aggregates': [],
      'linkTypes': []
      }
    for key, value in result.iteritems():
        if key in extra:
            result[key].extend(extra[key])
    result['types'].extend(calculate_types(is_basic, ads))
    result['images'].extend(calculate_images(is_basic, ads))
    result['hardware'].extend(calculate_hardware(is_basic, ads))
    result['aggregates'].extend(calculate_aggregates(is_basic, ads,
                                                     aggregateNames))
    result['linkTypes'].extend(calculate_link_types(is_basic, ads))
    return result


def calculate_types(is_basic, ads):
    found = make_initial_found(is_basic, advanced_types)
    result = []
    for ad in ads:
        for node in ad.nodes:
            for sliver_type in node.sliver_types:
                if sliver_type not in found:
                    result.append({'id': sliver_type,
                                   'name': sliver_type})
                    found[sliver_type] = 1
    return result


def calculate_images(is_basic, ads):
    found = make_initial_found(is_basic, advanced_images)
    result = []
    for ad in ads:
        for node in ad.nodes:
            cmurn = node.component_manager_id
            for sliver_name, images in node.images.iteritems():
                for image in images:
                    imageId = get_image_id(image, cmurn)
                    if imageId not in found:
                        description = image.description
                        if description is None:
                            description = imageId
                        # OpenGENI describes things as 'standard' and 'custom'
                        # so change them to the image id, which is a name
                        if description in ['standard', 'custom']:
                            description = imageId
                        imageResult = {'id': imageId,
                                       'name': description}
                        if imageId in nomac_images:
                            imageResult['nomac'] = True
                        result.append(imageResult)
                        found[imageId] = 1
    return result


def calculate_hardware(is_basic, ads):
    found = make_initial_found(is_basic, advanced_hardware)
    result = []
    for ad in ads:
        for node in ad.nodes:
            for name, slots in node.hardware_types.iteritems():
                if name not in found:
                    result.append({'id': name,
                                   'name': name})
                    found[name] = 1
    return result


def calculate_aggregates(is_basic, ads, aggregateNames):
    found = {}
    result = []
    for ad in ads:
        for node in ad.nodes:
            urn = node.component_manager_id
            name = urn
            if urn in aggregates['names']:
                name = aggregates['names'][urn]
            pieces = urn.split('+')
            if len(pieces) >= 1:
                name = pieces[1]
            if urn not in found:
                aggregateNames.append(urn)
                result.append({'id': urn,
                               'name': name})
                found[urn] = 1
    return result


def calculate_link_types(is_basic, ads):
    found = make_initial_found(is_basic, advanced_link_types)
    result = []
    for ad in ads:
        for link in ad.links:
            for link_type in link.link_types:
                if link_type not in found:
                    result.append({'id': link_type,
                                   'name': link_type})
                    found[link_type] = 1
    return result


def calculate_site_info(is_basic):
    result = {}
    for key in site_info.keys():
        result[key] = {}
        result[key]['types'] = site_info[key]['types'].keys()
        result[key]['hardware'] = site_info[key]['hardware'].keys()
    return result


def make_initial_found(is_basic, advanced_list):
    result = {}
    if is_basic:
        for item in advanced_list:
            result[item] = 1
    return result

##########################################################################


def calculate_context(is_basic, ads):
    aggregateNames = []
    canvas = calculate_canvas(is_basic, ads, aggregateNames)
    constraints = calculate_constraints(is_basic, ads, aggregateNames)
    if 'constraints' in extra:
        constraints.extend(extra['constraints'])
    canvas['site_info'] = calculate_site_info(is_basic)
    return {'canvasOptions': canvas,
            'constraints': constraints}


def get_advertisement(context, site, pipe, rspec_dir=None):
#    ad = site.listresources(context)
    try:
        ad = site.listresources(context)
        sys.stderr.write("[%s] Fetched Advertisement\n" % (site.name))
        (fd, path) = tempfile.mkstemp()
        with os.fdopen(fd, "w") as f:
            f.write(ad.text)
        pipe.send([path])
        if rspec_dir:
            rspec_path = os.path.join(rspec_dir, site.name)
            with open(rspec_path, 'w') as f:
                f.write(ad.text)
            sys.stderr.write("[%s] Wrote rspec to %s\n" % (site.name,
                                                           rspec_path))
    except Exception, e:
        pipe.send([])
        sys.stderr.write("[%s] OFFLINE\n" % (site.name))
    finally:
        pipe.close()


def do_parallel(is_basic=True, output=None, rspec_dir=None):
    # Note later updates will override earlier entries if they have the
    # same key.
    sites = geni.aggregate.loadFromRegistry(context)
    children = []
    pipes = []
    ads = []
    adFiles = []
    for site in sites.itervalues():
            pipe_parent, pipe_child = MP.Pipe(False)
            pipes.append(pipe_parent)
            p = MP.Process(target=get_advertisement,
                           args=(context, site, pipe_child, rspec_dir))
            p.start()
            children.append(p)
    for i in xrange(len(children)):
        child = children[i]
        pipe = pipes[i]
        adFiles.extend(pipe.recv())
        child.join()
    sys.stderr.write('Loading %d advertisements\n' % (len(adFiles)))
    for adFile in adFiles:
        with open(adFile, 'r') as f:
            adText = f.read()
        ads.append(Advertisement(xml=adText))
    sys.stderr.write("Processing %d advertisements\n" % len(ads))
    jacks_context = calculate_context(is_basic, ads)
    json_text = json.dumps(jacks_context, sort_keys=True, indent=2,
                           separators=(',', ': '))
    if output is not None:
        f = open(output, 'w+')
        f.write(json_text)
        f.close()
    else:
        print json_text
    sys.stderr.write("Processing complete\n")


def parse_config(file, is_basic):
    global advanced_types, advanced_hardware, advanced_images
    global advanced_link_types, extra, nomac_images, no_link
    global stitchable_ig, stitchable_eg, link_info, aggregates
    f = open(file, 'r')
    jsonText = f.read()
    f.close()
    config = json.loads(jsonText)
    if is_basic and 'advanced' in config:
        if 'types' in config['advanced']:
            advanced_types = config['advanced']['types']
        if 'hardware' in config['advanced']:
            advanced_hardware = config['advanced']['hardware']
        if 'images' in config['advanced']:
            advanced_images = config['advanced']['images']
        if 'linkTypes' in config['advanced']:
            advanced_link_types = config['advanced']['linkTypes']
    if 'aggregate_names' in config:
        aggregates['names'] = config['aggregate_names']
    if 'aggregate_types' in config:
        aggregates['types'] = config['aggregate_types']
    if 'extra' in config:
        extra = config['extra']
    if 'nomac_images' in config:
        nomac_images = config['nomac_images']
    if 'no_link' in config:
        no_link = config['no_link']
    if 'stitchable_ig' in config:
        stitchable_ig = config['stitchable_ig']
    if 'stitchable_eg' in config:
        stitchable_eg = config['stitchable_eg']
    if 'link_info' in config:
        link_info = config['link_info']


if __name__ == '__main__':
    #  global context
    parser = ArgumentParser()
    parser.add_argument('--config', dest='config', default=None,
                        help='Configuration file (json) for extra constraints')
    parser.add_argument('--output', dest='output', default=None,
                        help='Output path for Jacks context as JSON')
    parser.add_argument('--basic', dest='basic', default=False, const=True,
                        action='store_const',
                        help='Hide advanced options')
    parser.add_argument('--rspecdir', dest='rspecdir', default=None,
                        help='Directory for rspecs for debugging')
    parser.add_argument('--debug', dest='debug', default=False, const=True,
                        action='store_const',
                        help='Print extra debugging information')
    args = parser.parse_args()
    if args.debug:
        context.debug = True

    if args.config:
        parse_config(args.config, args.basic)
    do_parallel(is_basic=args.basic, output=args.output,
                rspec_dir=args.rspecdir)
