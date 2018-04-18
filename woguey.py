#!/usr/bin/python

import tcod as libtcod
import math
import textwrap
import shelve 

#size of window
SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

#size of map
MAP_WIDTH = 80
MAP_HEIGHT = 43

#size and coordinates for the gui panel
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2 
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT - 1
INVENTORY_WIDTH = 50
CHARACTER_SCREEN_WIDTH = 30
LEVEL_SCREEN_WIDTH = 40

#paramateres for dungeon generation
ROOM_MAX_SIZE = 15
ROOM_MIN_SIZE = 5
MAX_ROOMS = 40

#spell values
HEAL_AMOUNT = 40
TWERKING_DAMAGE = 40
TWERKING_RANGE = 5
GRINDING_DAMAGE = 80
GRINDING_RANGE = 4
CONFUSE_RANGE = 8
CONFUSE_NUM_TURNS = 10
GANGNAM_RANGE = 8
GANGNAM_RADIUS = 3
GANGNAM_DAMAGE = 25

#experience and levelups
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150

FOV_ALGO = 0 #pick fov algorithm 
FOV_LIGHT_WALLS = True #light walls or not
TORCH_RADIUS = 10

LIMIT_FPS = 20 #20 frames per second

color_dark_wall = libtcod.dark_pink
color_light_wall = libtcod.pink
color_dark_ground = libtcod.darkest_pink
color_light_ground = libtcod.lighter_pink

class Tile:
    #a tile of the map and its properties
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked

        #all tiles start unexplored
        self.explored = False

        #usually a blocked tile also blocks sight
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight

class Rect:
    #rectangle on the map
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h
    
    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return (center_x, center_y)
    
    def intersect(self, other):
        #return True if rectangles intersect
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)

class Object:
    #generic object on the screen
    def __init__(self, x, y, char, name, color, blocks=False, always_visible=False, fighter=None, ai=None, item=None, equipment=None):
        self.x = x
        self.y = y
        self.char = char
        self.name = name
        self.color = color
        self.blocks = blocks
        self.always_visible = always_visible
        self.fighter = fighter
        if self.fighter: #let the fiter know who owns it
            self.fighter.owner = self

        self.ai = ai
        if self.ai: #let the ai know who owns it
            self.ai.owner = self

        self.item = item
        if self.item: #let the item know who owns it
            self.item.owner = self

        self.equipment = equipment
        if self.equipment:
            self.equipment.owner = self

            #needs item component
            self.item = Item()
            self.item.owner = self

    def move(self, dx, dy):
        #move by given amount, if not blocked
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def move_towards(self, target_x, target_y):
        #vector from this object to target and distance
        dx = target_x - self.x
        dy = target_y - self.y 
        distance = math.sqrt(dx ** 2 + dy ** 2)

        #normalize to length 1
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def distance_to(self, other):
        #return distance to another object
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def send_to_back(self):
        #draw this first
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def draw(self):
        #only show if visible to player
        if (libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored)):
            #set color and draw in the correct place
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        #erase character
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

class Fighter:
    #combat properties of monsters, player, npcs
    def __init__(self, hp, defense, power, xp, death_function=None):
        self.base_max_hp = hp
        self.hp = hp
        self.base_defense = defense
        self.base_power = power
        self.xp = xp
        self.death_function = death_function

    @property
    def power(self):  #return actual power, by summing up the bonuses from all equipped items
        bonus = sum(equipment.power_bonus for equipment in get_all_equipped(self.owner))
        return self.base_power + bonus
 
    @property
    def defense(self):  #return actual defense, by summing up the bonuses from all equipped items
        bonus = sum(equipment.defense_bonus for equipment in get_all_equipped(self.owner))
        return self.base_defense + bonus
 
    @property
    def max_hp(self):  #return actual max_hp, by summing up the bonuses from all equipped items
        bonus = sum(equipment.max_hp_bonus for equipment in get_all_equipped(self.owner))
        return self.base_max_hp + bonus

    def attack(self, target):
        #battle formula
        damage = libtcod.random_get_int(0, 0, 2) * int(1 + ((2 * self.power) / (1 + target.fighter.defense))) + libtcod.random_get_int(0, 0, 6)

        if damage > 0:
            #make the target take damage
            message(self.owner.name.capitalize() + ' dabs on ' + target.name + ' for ' + str(damage) + ' CUMMIES!! XD')
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' tries to dab on ' + target.name + ' but wasn\'t ~squishy~ enough!!')

    def take_damage(self, damage):
        #apply damage if possible
        if damage > 0:
            self.hp -= damage

            #check for death
            if self.hp <= 0:
                function = self.death_function
                if function is not None:
                    function(self.owner)

                if self.owner != player:
                    player.fighter.xp += self.xp

    def heal(self, amount):
        #heal by given amount
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class BasicMonster:
    #ai for basic monster
    def take_turn(self):
        #if you see monster, monster sees you
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):

            #move towards the player if far away
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)

            #close enough, attack!(if player alive)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

class ConfusedMonster:
    #ai for confused monster
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns

    def take_turn(self):
        if self.num_turns > 0: #still confused
            #move in random direction
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -=1

        else: #restore previous ai
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!OWO', libtcod.red)

class Item:
    #an item that can be picked up and used
    def __init__(self, use_function=None):
        self.use_function = use_function

    def pick_up(self):
        #add to player inventory and remove from map
        if len(inventory) >= 26:
            message('Your inventory is ful!! Cannot pick up ' + self.owner.name + '!!~', libtcod.green)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '!!~~', libtcod.green)

            #special case for equipment
            equipment = self.owner.equipment
            if equipment and get_equipped_in_slot(equipment.slot) is None:
                equipment.equip()

    def drop(self):
        #special case for equipment
        if self.owner.equipment:
            self.owner.equipment.dequip()

        #add to the map and remove from inventory
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '!Owo', libtcod.yellow)

    def use(self):
        #special case for equipment
        if self.owner.equipment:
            self.owner.equipment.toggle_equip()
            return

        #call use function if defined
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used, silly!!uwu')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) #destroy after use unless cancelled 

class Equipment:
    #an object that can be equipped
    def __init__(self, slot, power_bonus=0, defense_bonus=0, max_hp_bonus=0):
        self.power_bonus = power_bonus
        self.defense_bonus = defense_bonus
        self.max_hp_bonus = max_hp_bonus

        self.slot = slot
        self.is_equipped = False

    def toggle_equip(self):
        if self.is_equipped:
            self.dequip()
        else:
            self.equip()

    def equip(self):
        #if slot is already used, dequip first
        old_equipment = get_equipped_in_slot(self.slot)
        if old_equipment is not None:
            old_equipment.dequip()

        #equip object and show message about it
        self.is_equipped = True
        message('Equipped ' + self.owner.name + ' on ' + self.slot + '.', libtcod.light_green)

    def dequip(self):
        #dequip object and show message about it
        if not self.is_equipped: return
        self.is_equipped = False
        message('Dequipped ' + self.owner.name + ' from ' + self.slot + '.', libtcod.light_yellow)

def get_equipped_in_slot(slot):
    for obj in inventory:
        if obj.equipment and obj.equipment.slot == slot and obj.equipment.is_equipped:
            return obj.equipment
    return None

def get_all_equipped(obj):
    if obj == player:
        equipped_list = []
        for item in inventory:
            if item.equipment and item.equipment.is_equipped:
                equipped_list.append(item.equipment)
        return equipped_list
    else:
        return [] #other objects have no equipment
        
def is_blocked(x, y):
    #first test the map tile
    if map[x][y].blocked:
        return True

    #now check for any blocking objects
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True
    
    return False

def create_room(room):
    global map
    #go thru tiles in rect and make them passable
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
    global map
    #horizontal tunnel
    for x in range(min(x1, x2), max(x1, x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
    global map
    #vertical tunnel
    for y in range(min(y1, y2), max(y1, y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def make_map():
    global map, objects, stairs

    #list of objects
    objects = [player]

    #fill map with "blocked" tiles
    map = [[ Tile(True)
        for y in range(MAP_HEIGHT) ]
            for x in range(MAP_WIDTH) ]
 
    rooms = []
    num_rooms = 0

    for r in range (MAX_ROOMS):
        #random width and height
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        #random position inside the map
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

        #Rect class makes rectangles easier to work
        new_room = Rect(x, y, w, h)

        #check intersecting rooms
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            #this means the room is valid

            #paint the room
            create_room(new_room)

            #center coordinates of new room
            (new_x, new_y) = new_room.center()

            #print "room number"
            #room_no = Object(new_x, new_y, chr(65+num_rooms), 'room number', libtcod.white)
            #objects.insert(0, room_no) #draw early

            if num_rooms == 0:
                #starting room
                player.x = new_x
                player.y = new_y
            else:
                #all other rooms
                #connect to previous room with tunnel

                #center coordinates of previous room
                (prev_x, prev_y) = rooms[num_rooms-1].center()

                #toss a coin
                if libtcod.random_get_int(0, 0, 1) == 1:
                    #first move h, then v
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    #first move v, then h
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)

            #add contents to room, like monsters
            place_objects(new_room)

            #finally the new room is appended to the list
            rooms.append(new_room)
            num_rooms += 1

    #create stairs at center of last room
    stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white, always_visible=True)
    objects.append(stairs)
    stairs.send_to_back()

def random_choice_index(chances): #choose one option from list of chances, return the index
    #dice will land between 1 and sum of chances
    dice = libtcod.random_get_int(0, 1, sum(chances))

    #go thru all chances, keeping the sum so far
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w

        #see if dice landed on choice
        if dice <= running_sum:
            return choice
        choice += 1

def random_choice(chances_dict):
    #choose option from dic of chances, return key
    chances = chances_dict.values()
    strings = chances_dict.keys()

    return strings[random_choice_index(chances)]

def from_dungeon_level(table):
    #returns a value that depends on level
    for (value, level) in reversed(table):
        if dungeon_level >= level:
            return value
    return 0

def place_objects(room):
    #maximum number of monsters per room per level
    max_monsters = from_dungeon_level([[2, 1], [3, 4], [5, 6]])

    #chance of each monster
    monster_chances = {}
    monster_chances['ugly'] = from_dungeon_level([[120, 1], [80, 2], [50, 3], [40, 10]])
    monster_chances['frogposter'] = from_dungeon_level([[120, 1], [80, 2], [50, 3], [40, 10]])
    monster_chances['nerdy'] = from_dungeon_level([[100, 1], [90, 2], [80, 3], [50, 10]])
    monster_chances['normie'] = from_dungeon_level([[100, 1], [90, 2], [80, 3], [50, 10]])
    monster_chances['qt'] = from_dungeon_level([[10, 1], [20, 2], [30, 3], [40, 4], [50, 5], [80, 6], [100, 8], [70, 10]])
    monster_chances['daddy'] = from_dungeon_level([[1, 1], [2, 2], [3, 3], [4, 4], [5, 5], [8, 6], [10, 8], [30, 10], [50, 12], [100, 15], [200, 20]])
    monster_chances['business'] = from_dungeon_level([[1, 1], [2, 2], [3, 3], [4, 4], [5, 5], [8, 6], [10, 8], [30, 10], [50, 12], [100, 15], [200, 20]])
    monster_chances['perfect'] = from_dungeon_level([[1, 10], [20, 15], [50, 20], [500, 50]])

    #maximum number of items per room per level
    max_items = from_dungeon_level([[1, 1], [2, 4], [3, 8]])

    #chance of each item
    item_chances = {}
    item_chances['heal'] = 35
    item_chances['twerking'] = from_dungeon_level([[25, 4], [50, 10]])
    item_chances['grinding'] = from_dungeon_level([[40, 8]])
    item_chances['gangnam'] = from_dungeon_level([[25, 6]])
    item_chances['confuse'] = from_dungeon_level([[10, 2]])
    item_chances['gloves'] =     from_dungeon_level([[10, 4]])
    item_chances['gold'] =     from_dungeon_level([[15, 10]])
    item_chances['skirt'] =    from_dungeon_level([[10, 5]])
    item_chances['mini'] =    from_dungeon_level([[15, 8]])


    #choose random number of monsters 
    num_monsters = libtcod.random_get_int(0, 0, max_monsters)  


    for i in range(num_monsters):
        #choose random spot for monster
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

        #only place if tile is not blocked
        if not is_blocked(x, y):
            #chances
            choice = random_choice(monster_chances)
            if choice == 'daddy':
                fighter_component = Fighter(hp=100, defense=10, power=20, xp=250, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'D', 'daddy', libtcod.white, blocks = True, fighter=fighter_component, ai=ai_component)

            if choice == 'business':
                fighter_component = Fighter(hp=80, defense=22, power=10, xp=250, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'B', 'businessman', libtcod.white, blocks = True, fighter=fighter_component, ai=ai_component)

            elif choice == 'perfect':
                fighter_component = Fighter(hp=300, defense=12, power=50, xp=5000, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'P', 'perfect DADDY', libtcod.white, blocks = True, fighter=fighter_component, ai=ai_component)

            elif choice == 'qt':
                fighter_component = Fighter(hp=30, defense=5, power=10, xp=100, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'q', 'qt3.14', libtcod.white, blocks = True, fighter=fighter_component, ai=ai_component)

            elif choice == 'nerdy':
                fighter_component = Fighter(hp=20, defense=1, power=4, xp=35, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'n', 'nerdy', libtcod.white, blocks = True, fighter=fighter_component, ai=ai_component)

            elif choice == 'normie':
                fighter_component = Fighter(hp=20, defense=2, power=2, xp=45, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'o', 'normie', libtcod.white, blocks = True, fighter=fighter_component, ai=ai_component)

            elif choice == 'ugly':
                fighter_component = Fighter(hp=12, defense=1, power=4, xp=15, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'u', 'ugly', libtcod.white, blocks = True, fighter=fighter_component, ai=ai_component)

            elif choice == 'frogposter':
                fighter_component = Fighter(hp=15, defense=1, power=1, xp=10, death_function=monster_death)
                ai_component = BasicMonster()

                monster = Object(x, y, 'f', 'dumb frogposter', libtcod.white, blocks = True, fighter=fighter_component, ai=ai_component)
            
            objects.append(monster)

    #choose random number of items
    num_items = libtcod.random_get_int(0, 0, max_items)

    for i in range(num_items):
        #choose random spot for item
        x = libtcod.random_get_int(0, room.x1+1, room.x2-1)
        y = libtcod.random_get_int(0, room.y1+1, room.y2-1)

        #only place if not blocked
        if not is_blocked(x, y):
            choice = random_choice(item_chances)
            if choice == 'heal':
                #create healing potion(70% chance)
                item_component = Item(use_function=cast_heal)

                item = Object(x, y, '!', 'jello shot', libtcod.violet, item=item_component)

            elif choice == 'twerking':
                #create a twerking scroll(10% chance)
                item_component = Item(use_function=cast_twerking)

                item = Object(x, y, '#', 'vodka', libtcod.light_yellow, item=item_component)

            elif choice == 'grinding':
                #create a grinding scroll(10% chance)
                item_component = Item(use_function=cast_grinding)

                item = Object(x, y, '#', 'absinthe', libtcod.light_yellow, item=item_component)

            elif choice == 'gangnam':
                #create gangnam scroll(10% chance)
                item_component = Item(use_function=cast_gangnam)

                item = Object(x, y, '#', 'whisky', libtcod.light_yellow, item=item_component)

            elif choice == 'confuse':
                #create a confusion item(10% chance)
                item_component = Item(use_function=cast_confuse)

                item = Object(x, y, '#', 'sangria', libtcod.light_yellow, item=item_component)

            elif choice == 'gloves':
                #create gloves
                equipment_component = Equipment(slot='accessories', power_bonus=5, defense_bonus=1, max_hp_bonus=10)
                item = Object(x, y, '/', 'dabbing gloves', libtcod.sky, equipment=equipment_component)

            elif choice == 'gold':
                #create gold ring
                equipment_component = Equipment(slot='accessories', power_bonus=8, defense_bonus=2, max_hp_bonus=20)
                item = Object(x, y, '/', 'gold ring', libtcod.sky, equipment=equipment_component)
 
            elif choice == 'skirt':
                #create a skirt
                equipment_component = Equipment(slot='clothes', power_bonus=1, defense_bonus=3, max_hp_bonus=30)
                item = Object(x, y, '[', 'skirt', libtcod.darker_orange, equipment=equipment_component)

            elif choice == 'mini':
                #create a mini-skirt
                equipment_component = Equipment(slot='clothes', power_bonus=2, defense_bonus=4, max_hp_bonus=50)
                item = Object(x, y, '[', 'mini-skirt', libtcod.darker_orange, equipment=equipment_component)
 
            objects.append(item)
            item.send_to_back() #appears below other obj
            item.always_visible = True

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    #render a bar, first calculate width
    bar_width = int(float(value) / maximum * total_width)

    #render background first
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)

    #render bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
    
    #some centered text with the values
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))

def get_names_under_mouse():
    global mouse 

    #return string with names of all objects under mouse
    (x, y) = (mouse.cx, mouse.cy)

    #create a list with the names in fov
    names = [obj.name for obj in objects
        if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]

    names = ', '.join(names) #join names separated by ,
    return names.capitalize()

def render_all():
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute

    if fov_recompute:
        #recompute fov if needed
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        #go through all tiles and set their background color
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    #the player can only see if explored
                    if map[x][y].explored:
                        if wall:
                            libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
                else:
                    #it's visible
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
                    #since it's visible, explore it
                    map[x][y].explored = True
            
    #draw all objects in list
    for object in objects:
        if object != player:
            object.draw()
    player.draw()

    #blit the contents of con to the root console
    libtcod.console_blit(con, 0, 0, MAP_WIDTH, MAP_HEIGHT, 0, 0, 0)

    #prepare to render gui panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)

    #print game messages one line at a time
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1

    #show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'CUMMIES', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)
    libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Club floor -' + str(dungeon_level))

    #display name of object under mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_gray)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

    #blit contents of panel to root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def message(new_msg, color = libtcod.white):
    #split message if necessary
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)

    for line in new_msg_lines:
        #if buffer is full, remove first line
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]

        #add the new line as tuple with text and color
        game_msgs.append( (line, color) )

def player_move_or_attack(dx, dy):
    global fov_recompute

    #the coordinates the player is moving to/attk
    x = player.x + dx
    y = player.y + dy

    #try to find attackable object there
    target = None
    for object in objects:
        if object.fighter and object.x == x and object.y == y:
            target = object
            break

    #attack if target found, move otherwise
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True

def menu(header, options, width):
    if len(options) > 26: raise ValueError('CANNOT HAVE MORE THAN 26 OPTIONS YOU SILLY WILLY!!!')

    #calculate total height for header
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    if header == '':
        header_height = 0
    height = len(options) + header_height

    #create off-screen console for menu window
    window = libtcod.console_new(width, height)
    
    #print the header, with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

    #print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ')' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1

    #blit window contents to the root console
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    #present the root console and wait for keypress
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)

    #convert ascii code to an index, if it is an option, return it
    index = key.c - ord('a')
    if index >= 0 and index < len(options): return index
    return None

def inventory_menu(header):
    #show a menu with each item of the inventory 
    if len(inventory) == 0:
        options = ['YOU HAVE NUFFIN! XD']
    else:
        options = []
        for item in inventory:
            text = item.name
            #show additional information, in case it's equipped
            if item.equipment and item.equipment.is_equipped:
                text = text + ' (on ' + item.equipment.slot + ')'
            options.append(text)
    
    index = menu(header, options, INVENTORY_WIDTH)

    #if item was chosen, return it
    if index is None or len(inventory) == 0: return None
    return inventory[index].item

def msgbox(text, width=50):
    menu(text, [], width) #use menu() as a msgbox

def handle_keys():
    global key

    if key.vk == libtcod.KEY_ESCAPE:
        return 'exit' #exit game

    if game_state == 'playing':
        #movement keys
        if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1, -1)
        elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1, -1)
        elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)
        elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1, 1)
        elif key.vk == libtcod.KEY_KP5:
            pass  #do nothing ie wait for the monster to come to you
        else:
            #test for other keys
            key_char = chr(key.c)

            if key_char == 'g':
                #pick up an item
                for object in objects: 
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break

            if key_char == 'i':
                #show inventory
                chosen_item = inventory_menu('Pwess key next to item to use or any other to cancel! Uwu \n')
                if chosen_item is not None:
                    chosen_item.use()

            if key_char == 'd':
                #show inventory, if an item is selected, drop it
                chosen_item = inventory_menu('Pwess key next to item to drop it, or any other to cancel!!OWO \n')
                if chosen_item is not None:
                    chosen_item.drop()

            if key_char == 'c':
                #show character information
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox('Your bio!\n\nLevel: ' + str(player.level) + '\nExperience: ' + str(player.fighter.xp) + 
                    '\nExperience to level up: ' + str(level_up_xp) + '\n\nMaximum Cummies: ' + str(player.fighter.max_hp) + 
                    '\nBeauty: ' + str(player.fighter.power) + '\nStyle: ' + str(player.fighter.defense), CHARACTER_SCREEN_WIDTH)

            if key_char == '<':
                #go down stairs if player is on
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()

            return 'didnt-take-turn'

def check_level_up():
    #see if the player's exp is enough to levelup
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        #it is!! level up
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('You got squishier! You weached level ' + str(player.level) + '!', libtcod.yellow)

        choice = None
        while choice == None:
            choice = menu('Level up! Choose stat to raise:\n', 
                ['Standards (+20 CUMMIES, from ' + str(player.fighter.max_hp) + ')',
                'Cuteness (+1 Beauty, from ' + str(player.fighter.power) + ')',
                'Stylishness (+1 Style, from ' + str(player.fighter.defense) + ')'], LEVEL_SCREEN_WIDTH)

        if choice == 0:
            player.fighter.base_max_hp += 20
            player.fighter.hp += 20
        elif choice == 1:
            player.fighter.base_power += 1
        elif choice == 2:
            player.fighter.base_defense += 1

def player_death(player):
    #the game ended!
    global game_state
    message('You lost your CUMMIES! UWU', libtcod.red)
    game_state = 'dead'

    #transform player into corpse
    player.char = '%'
    player.color = libtcod.dark_red

def monster_death(monster):
    #transform into corpse
    message(monster.name.capitalize() + ' lost all his CUMMIES! U gain ' + str(monster.fighter.xp) + ' sexy exp points.', libtcod.orange)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()

def closest_monster(max_range):
    #find closest enemy inside player's fov
    closest_enemy = None
    closest_dist = max_range + 1

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            #calculate distance
            dist = player.distance_to(object)
            if dist < closest_dist:
                closest_enemy = object
                closest_dist = dist
    return closest_enemy

def cast_heal():
    #heal the player
    if player.fighter.hp == player.fighter.max_hp:
        message('YOU HAVE ALL YOUR CUMMIES!!UWU', libtcod.red)
        return 'cancelled'
    
    message('You replenished your cummies! Yum!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_twerking():
    #find closest enemy and damage it
    monster = closest_monster(TWERKING_RANGE)
    if monster is None:
        message('No ~squishies~ close enough.', libtcod.red)
        return 'cancelled'

    #twerk on it
    message('You start twerking on ' + monster.name + ' and make him lose ' + str(TWERKING_DAMAGE) + ' CUMMIES!', libtcod.light_blue)
    monster.fighter.take_damage(TWERKING_DAMAGE)

def cast_grinding():
    #find closest enemy and damage it
    monster = closest_monster(GRINDING_RANGE)
    if monster is None:
        message('No ~squishies~ close enough.', libtcod.red)
        return 'cancelled'

    #grind on it
    message('You start grinding on ' + monster.name + ' and make him lose ' + str(GRINDING_DAMAGE) + ' CUMMIES!', libtcod.light_blue)
    monster.fighter.take_damage(GRINDING_DAMAGE)

def cast_gangnam():
    monster = closest_monster(GANGNAM_RANGE)
    if monster is None:
        message('Don\'t be silly!! No one is in range!', libtcod.red)
        return 'cancelled'
    
    #OPA OPA OPA GANGNAM STYLE
    message('Everyone suffers through your Gangnam Style within ' + str(GANGNAM_RADIUS) + ' tiles!', libtcod.orange)

    for obj in objects:
        if obj.distance_to(monster) <= GANGNAM_RADIUS and obj.fighter and obj != player:
            message('The ' + obj.name + ' gets pwned for ' + str(GANGNAM_DAMAGE) + ' CUMMIES!', libtcod.orange)
            obj.fighter.take_damage(GANGNAM_DAMAGE)

def cast_confuse():
    #find closest enemy in-range and confuse it
    monster = closest_monster(CONFUSE_RANGE)
    if monster is None: #no enemy in range
        message('Nobody can see you dance the macarena!', libtcod.red)
        return 'cancelled'
    #replace ai with a confused ai
    old_ai = monster.ai
    monster.ai = ConfusedMonster(old_ai)
    monster.ai.owner = monster
    message(monster.name + ' is confused by your dance from the 90s?!?!', libtcod.light_green)

def save_game():
    #open a new empty shelve (possibly overwriting an old one) to write the game data
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player)  #index of player in objects list
    file['stairs_index'] = objects.index(stairs)
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['dungeon_level'] = dungeon_level
    file.close()

def load_game():
    #open the previously saved shelve and load the game data
    global map, objects, player, stairs, inventory, game_msgs, game_state, dungeon_level
 
    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']]  #get index of player in objects list and access it
    stairs = objects[file['stairs_index']]
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    dungeon_level = file['dungeon_level']
    file.close()
 
    initialize_fov()

def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level

    #create player object
    fighter_component = Fighter(hp=100, defense=1, power=2, xp=0, death_function=player_death)
    player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)

    player.level = 1

    #generate map, still not drawn
    dungeon_level = 1
    make_map()
    initialize_fov()

    game_state = 'playing'
    inventory = []

    #create list of game messages and colors, starts empty
    game_msgs = []

    #welcoming message
    message("Welcome to the BIG PARTY~~! XD DON'T LOSE YOUR CUMMIES XD uwu")

    #initial equipment: ring
    equipment_component = Equipment(slot='accessories', power_bonus=2)
    obj = Object(0, 0, '/', 'candy ring', libtcod.sky, equipment=equipment_component)
    inventory.append(obj)
    equipment_component.equip()
    obj.always_visible = True

def next_level():
    #advance to next level
    global dungeon_level 
    message('You recover some cummies as you go down the stairs', libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp / 2)

    dungeon_level += 1
    message('You go down one room and try to find the perfect daddy', libtcod.red)
    make_map() #create a fresh new level
    initialize_fov()

def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True

    #create the fov map, according to generated map
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

    libtcod.console_clear(con) #unexplored areas start black 

def play_game():
    global key, mouse

    player_action = None

    mouse = libtcod.Mouse()
    key = libtcod.Key()
    while not libtcod.console_is_window_closed():
        
        #render the screen
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        render_all()

        libtcod.console_flush()

        #level up if needed
        check_level_up()

        #erase all objects before they move
        for object in objects:
            object.clear()

        #handle keys and exit game if needed
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        #let monsters take their turn
        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()

def main_menu():
    img = libtcod.image_load('kawaii.png')

    while not libtcod.console_is_window_closed():
        #show bkgnd img at twice the size
        libtcod.image_blit_2x(img, 0, 0, 0)

        #show game title and credits
        libtcod.console_set_default_foreground(0, libtcod.purple)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER, '~WOGUEY WIKEY~')
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER, 'by n8uv')

        #show options and wait for the player's choice
        choice = menu('', ['Pway a new game!', 'Return to Daddy', 'Quit OwO'], 24)

        if choice == 0: #new game
            new_game()
            play_game()
        if choice == 1: #load last game
            try:
                load_game()
            except:
                msgbox('\n u dont have saved game \n', 24)
                continue
            play_game()
        elif choice == 2: #quit
            break

libtcod.console_set_custom_font('arial12x12.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, '~Woguey Wikey~', False)
libtcod.sys_set_fps(LIMIT_FPS)
con = libtcod.console_new(MAP_WIDTH, MAP_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)

main_menu()






