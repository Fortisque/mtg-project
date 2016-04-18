"""
This is where everything happens.
Uses the labels and color info from an arbitrary
image to create a relevant magic card.
"""

import math
import collections
import random

def closest_color(red, green, blue):
  """
  Determines whether the RBG value is closer to white, blue
  green, red, black or not really any of them.
  Theory taken from
  http://stackoverflow.com/questions/12069494/rgb-similar-color-approximation-algorithm
  """
  my_ycc = _ycc(red, green, blue)
  choices = [('red', _ycc(255, 0, 0)), ('blue', _ycc(0, 0, 255)), ('green', _ycc(0, 0, 150)), ('black', _ycc(0, 0, 0)), ('white', _ycc(255, 255, 255))]
  results = []
  for choice in choices:
    y1, cb1, cr1 = my_ycc
    y2, cb2, cr2 = choice[1]
    diff = math.sqrt(1.4*math.pow(y1-y2, 2) + .8*math.pow(cb1-cb2, 2) + .8*math.pow(cr1-cr2, 2))
    results.append((choice[0], diff))

  sorted_results = sorted(results, key=lambda x: x[1])
  best_match = sorted_results[0]
  import pdb; pdb.set_trace()
  if best_match[1] < 100:
    # 100 is kind of arbitrary...but need a way to get rid colors that 
    # are just not close to any other color
    return best_match[0]
  return None


def _ycc(r, g, b): # in (0,255) range
  """
  Converts RBG into ycc color space which should be able to more accurately
  predict colors.
  """
  y = .299*r + .587*g + .114*b
  cb = 128 -.168736*r -.331364*g + .5*b
  cr = 128 +.5*r - .418688*g - .081312*b
  return y, cb, cr

def get_card_database():
  """
  Loads in a bunch of cards we have pre generated.
  We'll sort the cards into what color they are, and then
  attempt to grab one of these cards as a base for the card we are generating.

  This assumes the database of cards is saved at 'large_sample_readable.cards'
  """
  filename = 'large_final_sample_readable.cards'
  database = collections.defaultdict(list)
  cards_sample = open(filename, 'r')
  content = cards_sample.read()
  # the cards are split by \n\n from mtgencode
  cards = content.split('\n\n')
  possible_colors = {'R' : 'Red', 'U' : 'Blue', 'G' : 'Green', 'B' : 'Black', 'W' : 'White'}
  for card in cards:
    if '~~~~~~~~' in card:
      # not a real card, some kind of marker.
      continue
    lines = card.split('\n')
    first_line = lines[0] # first line has mana cost info
    mana_cost = first_line.split(' ')[-1]

    colors = []
    # stable order with the sort
    keys = sorted(possible_colors.keys())
    for color in keys:
      if color in mana_cost:
        colors.append(possible_colors[color])

    colors_string = ','.join(colors)
    database[colors_string].append(card)

  return database

def get_flavor_database():
  """
  Loads in a bunch of flavor texts we have pre generated.
  We'll attempt to grab one of these that is related to the image
  we are generating from.

  This assumes the database of flavor is saved at 'legacy_flavor.txt'
  """
  filename = 'legacy_flavor.txt'
  database = []
  flavor = open(filename, 'r')
  content = flavor.read()
  # the flavor is split by \n\n from mtgencode
  flavors = content.split('\n\n')
  for flavor in flavors:
    if '~~~~~~~~' in flavor:
      # not a real card, some kind of marker.
      continue
    flavor = flavor.replace('|', '')
    flavor = flavor.replace('`', '')
    database.append(flavor)

  return database


class CardGenerator:

  def __init__(self, labels, color_info, debug=False):
    self.labels = labels
    self.color_info = color_info
    self.generated = False
    self.debug = debug

  def generate_card_color(self):
    # uses color info to get an appropriate color
    votes = collections.defaultdict(int)
    for single_color_info in self.color_info:
      rbg_values = single_color_info['color']
      color_vote = closest_color(rbg_values['red'], rbg_values['green'], rbg_values['blue'])
      votes[color_vote] += 1 * single_color_info['pixelFraction'] * single_color_info['score']
    sorted_votes = sorted(votes.items(), key=lambda x: x[1])
    if self.debug:
      print "Votes for color choice: %s\n" % sorted_votes
    if len(sorted_votes) > 1:
      best_match = sorted_votes[-1]
      self.color = best_match[0].capitalize()
      if self.debug:
        print "Color chosen: %s\n" % self.color
      # should check for second best match for multi color?
    else:
      self.color = None

  def generate_playable_card(self):
    # uses color, and labels to generate a name and all relevant abilities
    database = get_card_database()

    choices = database[self.color]
    names = []
    found_indicies = []
    for index, card in enumerate(choices):
      lines = card.split('\n')
      name_and_mana_cost = lines[0].split()
      name = ' '.join(name_and_mana_cost[:-1])
      names.append(name)

      for label in self.labels:
        if label in name:
          # good enough of a match for me...
          found_indicies.append(index)
          if self.debug:
            print "Matching %s label with %s" % (label, name)

    if len(found_indicies) != 0:
      index = random.choice(found_indicies)
      card = choices[index]
    else:
      card = random.choice(database[self.color])

    lines = card.split('\n')
    name_and_mana_cost = lines[0].split()
    self.name = ' '.join(name_and_mana_cost[:-1])
    self.mana_cost = name_and_mana_cost[-1]
    self.type = lines[1]
    if 'creature' in self.type:
      self.rules = '\n'.join(lines[2:-1])
      self.power_toughness = lines[-1]
    else:
      self.rules = '\n'.join(lines[2:])
      self.power_toughness = None

  def generate_card_flavor_text(self):
    # uses the labels of the image to find a relevant flavor text
    # Uses word2vec to try to find flavor similar to the labels

    flavor_database = get_flavor_database()
    try:
      from gensim import corpora, models, similarities
      stoplist = set('for a of the and to in'.split())
      texts = [[word for word in flavor.lower().split() if word not in stoplist]
                for flavor in flavor_database]

      dictionary = corpora.Dictionary(texts)
      corpus = [dictionary.doc2bow(text) for text in texts]

      lsi = models.LsiModel(corpus, id2word=dictionary)
      doc = ' '.join(self.labels)
      vec_bow = dictionary.doc2bow(doc.lower().split())
      vec_lsi = lsi[vec_bow]
      index = similarities.MatrixSimilarity(lsi[corpus])
      sims = index[vec_lsi]
      sims = sorted(enumerate(sims), key=lambda item: -item[1])

      # kind of arbitrary, choice a random from the top 10 to spice it up.
      best_matches = sims[:10]
      if self.debug:
        best_flavors = map(lambda x: flavor_database[x[0]], best_matches)
        print "Flavor choices %s" % best_flavors
      best_match = random.choice(best_matches)
      index, score = best_match
      self.flavor = flavor_database[index]
    except ImportError:
      print("Tried to import gensim for flavor text matching, just using random instead")
      self.flavor = random.choice(flavor_database)

  def generate(self):
    # Triggers generation of the card.
    self.generate_card_color()
    self.generate_playable_card()
    self.generate_card_flavor_text()
    self.generated = True

  def __str__(self):
    # For printing cards. Better readability, but doesn't look that great
    if not self.generated:
      return "call generate first!"
    attributes = ["Color: %s" % self.color, "Name: %s" % self.name]
    attributes += ["Rules: %s" % self.rules, "Flavor: %s" % self.flavor]
    attributes += ["Mana cost: %s" % self.mana_cost, "Type: %s" % self.type]
    if self.power_toughness:
      attributes += ['Power/Toughness: %s' % self.power_toughness]
    return "\n".join(attributes)

