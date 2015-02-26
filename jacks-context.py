#!/usr/bin/env python

# Copyright (c) 2014  Barnstormer Softworks, Ltd.

import multiprocessing as MP
from argparse import ArgumentParser
import time
import json
import sys
import os

import config
import geni.aggregate.instageni as IG
import geni.aggregate.exogeni as EXO
import geni.aggregate.opengeni as OG
import geni.aggregate.protogeni as PG
import geni.aggregate.cloudlab as CL
import geni.aggregate.apt as APT
from geni.rspec.pgad import Advertisement

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
stitchable_ig = []
stitchable_eg = []
link_info = {
  'local': [],
  'tunnel': [],
  'stitch-ig': [],
  'stitch-eg': []
}

context = config.buildContext()

##########################################################################

class ConstraintPair:
  def __init__(self):
    self.aCount = {};
    self.bCount = {};
    self.comboCount = {};
    self.aSeen = {};
    self.bSeen = {};
    self.comboSeen = {};

  # Reset seen markers because there is a new node
  def newNode(self):
    self.aSeen = {};
    self.bSeen = {};
    self.comboSeen = {};

  # Mark a combination as being available on this node
  def addPair(self, a, b):
    # Add a to the count if it hasn't been seen
    if not a in self.aSeen:
      if not a in self.aCount:
        self.aCount[a] = 0
      self.aCount[a] += 1
      self.aSeen[a] = 1
    # Add b to the count if it hasn't been seen
    if not b in self.bSeen:
      if not b in self.bCount:
        self.bCount[b] = 0
      self.bCount[b] += 1
      self.bSeen[b] = 1
    # Add the pair (a, b) to the count if it hasn't been seen
    if not a in self.comboCount:
      self.comboCount[a] = {}
    if not a in self.comboSeen:
      self.comboSeen[a] = {}
    if not b in self.comboSeen[a]:
      if not b in self.comboCount[a]:
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
  result.extend(calculate_type_link(is_basic, ads, aggregateNames))
  return result

def get_image_id(image, cmurn):
  #imageId = image.url
  #if imageId is None:
  #  imageId = image.name
  imageId = image.name
  if cmurn in aggregates['types'] and aggregates['types'][cmurn] == 'ig':
    urn = imageId
    baseId = urn.split('+')[-1]
    imageId = 'urn:publicid:IDN+emulab.net+image+' + baseId
  return imageId


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
        if not name in advanced_types:
          pair.addPair(name, '!')
      for sliver_name, images in node.images.iteritems():
        for image in images:
          imageId = get_image_id(image, cmurn)
          if not is_basic or (not sliver_name in advanced_types and
                              not imageId in advanced_images):
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
        if not name in advanced_types:
          pair.addPair(name, '!')

      hardwarenames = []
      for name, slots in node.hardware_types.iteritems():
        if not name in advanced_hardware:
          pair.addPair('!', name)

      for hardware_name, slots in node.hardware_types.iteritems():
        for sliver_name in node.sliver_types:
          if not is_basic or (not sliver_name in advanced_types and
                              not hardware_name in advanced_hardware):
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

def calculate_type_link(is_basic, ads, aggregateNames):
  result = []
  if len(link_info['stitch-ig']) > 0:
    add_stitchable_constraints(stitchable_ig,
                               link_info['stitch-ig'], result)
  if len(link_info['stitch-eg']) > 0:
    add_stitchable_constraints(stitchable_eg,
                               link_info['stitch-eg'], result)
  if len(link_info['tunnel']) > 0:
    result.append({
      'node': { 'aggregates': ['*'] },
      'link': { 'linkTypes': link_info['tunnel'] },
      'node2': { 'aggregates': ['*'] }
    })
  if len(link_info['local']) > 0:
    for urn in aggregateNames:
      result.append({
        'node': { 'aggregates': [urn] },
        'link': { 'linkTypes': link_info['local'] },
        'node2': { 'aggregates': [urn] }
      })

  return result

def add_stitchable_constraints(list, linkType, result):
  for urn in list:
    others = find_not(list, urn)
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
    if item != without:
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
  result['aggregates'].extend(calculate_aggregates(is_basic, ads, aggregateNames))
  result['linkTypes'].extend(calculate_link_types(is_basic, ads))
  return result

def calculate_types(is_basic, ads):
  found = make_initial_found(is_basic, advanced_types)
  result = []
  for ad in ads:
    for node in ad.nodes:
      for sliver_type in node.sliver_types:
        if not sliver_type in found:
          result.append({ 'id': sliver_type,
                          'name': sliver_type })
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
          if cmurn == 'urn:publicid:IDN+clemson-clemson-control-1.clemson.edu+authority+am':
            print image
          imageId = get_image_id(image, cmurn)
          #if imageId == 'centos-6.5':
          #  print cmurn, image
          if not imageId in found:
            description = image.description
            if description is None:
              description = imageId
            imageResult = { 'id': imageId,
                            'name': description }
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
        if not name in found:
          result.append({ 'id': name,
                          'name': name })
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
      if not urn in found:
        aggregateNames.append(urn)
        result.append({ 'id': urn,
                        'name': name })
        found[urn] = 1
  return result

def calculate_link_types(is_basic, ads):
  found = make_initial_found(is_basic, advanced_link_types)
  result = []
  for ad in ads:
    for link in ad.links:
      for link_type in link.link_types:
        if not link_type in found:
          result.append({ 'id': link_type,
                          'name': link_type })
          found[link_type] = 1
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
  return {'canvasOptions': canvas,
          'constraints': constraints }

def get_advertisement (context, site, pipe, rspec_dir=None):
  try:
    ad = site.listresources(context)
    pipe.send([ad.text])
    sys.stderr.write("[%s] Fetched Advertisement\n" % (site.name))
    if rspec_dir:
      rspec_path = os.path.join(rspec_dir, site.name)
      with open(rspec_path, 'w') as f:
        f.write(ad.text)
      sys.stderr.write("[%s] Wrote rspec to %s\n" % (site.name, rspec_path))
  except Exception, e:
    pipe.send([])
    sys.stderr.write("[%s] OFFLINE\n" % (site.name))
  pipe.close()

def do_parallel (is_basic=True, sites=[], output=None, rspec_dir=None):
  aggmapping = dict()
  # Note later updates will override earlier entries if they have the
  # same key.
  aggmapping.update(APT.name_to_aggregate())
  aggmapping.update(CL.name_to_aggregate())
  aggmapping.update(PG.name_to_aggregate())
  aggmapping.update(OG.name_to_aggregate())
  aggmapping.update(EXO.name_to_aggregate())
  aggmapping.update(IG.name_to_aggregate())
  children = []
  pipes = []
  ads = []
  for site_name in sites:
    site = None
    if site_name in aggmapping:
      site = aggmapping[site_name]
    if site:
      pipe_parent, pipe_child = MP.Pipe(False)
      pipes.append(pipe_parent)
      p = MP.Process(target=get_advertisement,
                     args=(context, site, pipe_child, rspec_dir))
      p.start()
      children.append(p)
  for i in xrange(len(children)):
    child = children[i]
    pipe = pipes[i]
    try:
      adTexts = pipe.recv()
      #f = open('ads.txt', 'w+')
      for adText in adTexts:
        #f.write(adText)
        #f.write('\n\n\n\n')
        ads.append(Advertisement(xml=adText))
      #f.close()
    except EOFError, e:
      pass
    child.join()
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
  global advanced_types, advanced_hardware, advanced_images, advanced_link_types, extra, nomac_images, stitchable_ig, stitchable_eg, link_info, aggregates
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
  if 'stitchable_ig' in config:
    stitchable_ig = config['stitchable_ig']
  if 'stitchable_eg' in config:
    stitchable_eg = config['stitchable_eg']
  if 'link_info' in config:
    link_info = config['link_info']

if __name__ == '__main__':
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
  parser.add_argument('site', nargs='+',
                      help='InstaGENI Site names ex: ig-utah')
  args = parser.parse_args()

  if args.config:
    parse_config(args.config, args.basic)
  do_parallel(is_basic=args.basic, sites=args.site, output=args.output,
              rspec_dir=args.rspecdir)
