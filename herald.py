#!/usr/bin/env python3
"""
Herald v0.1 - Hunger & Movement Demo
You are the LLM! Give Herald commands or let him roam.
"""

import time
import random
import os
import sys
import select
from datetime import datetime

class World:
    """The game world - a simple grid with food spawning"""
    
    def __init__(self, width=5, height=5):
        self.width = width
        self.height = height
        self.food_locations = set()
        self.spawn_initial_food()

    
    def spawn_initial_food(self):
        """Put some food in random locations"""
        for _ in range(8):
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)
            self.food_locations.add((x, y))
    
    def has_food_at(self, x, y):
        """Check if there's food at this location"""
        return (x, y) in self.food_locations
    
    def remove_food_at(self, x, y):
        """Remove food after it's eaten"""
        self.food_locations.discard((x, y))
    
    def is_valid_position(self, x, y):
        """Check if coordinates are within world bounds"""
        return 0 <= x < self.width and 0 <= y < self.height


class Herald:
    """Herald - our NPC who gets hungry and needs to eat"""
    
    def __init__(self, world, x=2, y=2):        
        self.world = world
        self.x = x
        self.y = y
        self.hunger = 0  # 0 = full, 100 = starving
        self.hunger_rate = 5  # Hunger increases by this each tick
        self.alive = True
        self.actions_taken = []
        
    def tick(self):
        """Called each game tick - hunger increases over time"""
        if self.alive:
            self.hunger += self.hunger_rate
            if self.hunger >= 100:
                self.hunger = 100
                self.alive = False
                self.log_action("DIED", "Herald starved to death!")
    
    def move(self, direction):
        """Move in a direction: north, south, east, west"""
        old_x, old_y = self.x, self.y
        
        if direction == "north":
            self.y -= 1
        elif direction == "south":
            self.y += 1
        elif direction == "east":
            self.x += 1
        elif direction == "west":
            self.x -= 1
        else:
            return False, "Invalid direction"
        
        # Check if move is valid
        if not self.world.is_valid_position(self.x, self.y):
            # Move back if out of bounds
            self.x, self.y = old_x, old_y
            return False, "Can't move there - out of bounds"
        
        self.log_action("MOVE", f"Moved {direction} to ({self.x}, {self.y})")
        return True, f"Moved {direction}"
    
    def eat(self):
        """Eat food if present at current location"""
        if self.world.has_food_at(self.x, self.y):
            self.world.remove_food_at(self.x, self.y)
            self.hunger = max(0, self.hunger - 50)  # Eating reduces hunger
            self.log_action("EAT", f"Ate food at ({self.x}, {self.y}). Hunger now: {self.hunger}")
            return True, "Ate food! Yum!"
        else:
            return False, "No food here to eat"
    
    def get_status(self):
        """Return Herald's current state"""
        status = "ALIVE" if self.alive else "DEAD"
        hunger_desc = self.get_hunger_description()
        return {
            "status": status,
            "location": (self.x, self.y),
            "hunger": self.hunger,
            "hunger_desc": hunger_desc,
            "sees_food": self.world.has_food_at(self.x, self.y)
        }
    
    def get_hunger_description(self):
        """Human-readable hunger level"""
        if self.hunger < 20:
            return "Full"
        elif self.hunger < 40:
            return "Satisfied"
        elif self.hunger < 60:
            return "Getting hungry"
        elif self.hunger < 80:
            return "Very hungry"
        else:
            return "STARVING"
        

    def look_around(self, vision_range= 4):
        """Look around for food within vision range"""
        nearest_food = None
        nearest_distance = float('inf')

        for dx in range(-vision_range, vision_range + 1):
            for dy in range(-vision_range, vision_range + 1):
                check_x = self.x + dx
                check_y = self.y + dy

                if not self.world.is_valid_position(check_x, check_y):
                    continue

                if self.world.has_food_at(check_x, check_y):
                    distance = abs(dx) + abs(dy)

                    if distance < nearest_distance:
                            nearest_distance = distance
                            nearest_food = (check_x, check_y)
        return nearest_food
    
    def move_toward(self, target_x, target_y):
        """move one stop toward target location"""
        dx = target_x - self.x
        dy = target_y - self.y

        print(f"[DEBUG move_toward] Target: ({target_x}, {target_y}), Current: ({self.x}, {self.y}), dx={dx}, dy={dy}")
    
        # If already at target
        if dx == 0 and dy == 0:
            print("[DEBUG] Already at target!")
            return False, "Already here"
        
        if abs(dx) > abs(dy):
        # Move horizontally
            if dx > 0:
                print("[DEBUG] Moving east")
                return self.move("east")
            else:
                print("[DEBUG] Moving west")
                return self.move("west")
        elif abs(dy) > abs(dx):
            # Move vertically
            if dy > 0:
                print("[DEBUG] Moving south")
                return self.move("south")
            else:
                print("[DEBUG] Moving north")
                return self.move("north")
        else:
            # Equal distance - choose randomly or prefer one direction
            if dx != 0:
                if dx > 0:
                    print("[DEBUG] Moving east (equal distance)")
                    return self.move("east")
                else:
                    print("[DEBUG] Moving west (equal distance)")
                    return self.move("west")
            elif dy != 0:
                if dy > 0:
                    print("[DEBUG] Moving south (equal distance)")
                    return self.move("south")
                else:
                    print("[DEBUG] Moving north (equal distance)")
                    return self.move("north")
    
    def log_action(self, action_type, description):
        """Log what Herald does (for future LLM context)"""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "type": action_type,
            "description": description,
            "state": self.get_status()
        }
        self.actions_taken.append(entry)
        
        # Keep only last 20 actions (memory limit)
        if len(self.actions_taken) > 20:
            self.actions_taken.pop(0)


class Game:
    """The game controller - handles UI and game loop"""
    
    def __init__(self):
        self.running = True
        self.auto_mode = False
        self.step_mode = False
        self.tick_count = 0
        self.world = None
        self.herald = None

        self.reset_world(show_message=False)

    def reset_world(self, show_message=True):
        """Reset the world and Herald to starting state"""
        self.world = World(width=10, height=10)
        self.herald = Herald(self.world, x=5, y=5)
        self.tick_count = 0
        self.auto_mode = False
        
        if show_message:
            print("→ World reset! Herald lives again!")

    def check_for_stop_command(self):
        """Check if user pressed a key without blocking"""    
        if select.select([sys.stdin], [], [], 0)[0]:
            key = sys.stdin.readline().strip()
            if key.lower() == 'x':
                return True
        return False
    
    def draw_world(self):
        """Display the world grid"""
        
        os.system('clear')
        print("\nCOMMANDS: {self.get_command_summary()}")
        print("\n" + "="*70)
        print(f"TICK {self.tick_count} | Herald's World")
        print("="*70)
        
        # Draw grid
        for y in range(self.world.height):
            row = ""
            for x in range(self.world.width):
                if self.herald.x == x and self.herald.y == y:
                    row += " H "  # Herald
                elif self.world.has_food_at(x, y):
                    row += " F "  # Food
                else:
                    row += " . "  # Empty
            print(row)
        
        print()
        
        # Show status
        status = self.herald.get_status()
        print(f"Status: {status['status']}")
        print(f"Location: {status['location']}")
        print(f"Hunger: {status['hunger']}/100 ({status['hunger_desc']})")
        print(f"Food here: {'YES' if status['sees_food'] else 'NO'}")
        print()
    
    def show_help(self):
        """Display available commands"""
        commands = [
            "  move <direction>  - Move north/south/east/west"
            "  eat               - Eat food if present"
            "  wait              - Do nothing this turn"
            "  status            - Show Herald's current state"
            "  auto              - Let Herald roam on his own"
            "  stop              - Stop auto mode"
            "  help              - Show this help"
            "  quit              - Exit game"
        ]

        print("\nCOMMANDS:")
        for cmd in commands:
            print(f"    {cmd}")
        print()

        return commands
    
    def get_command_summary(self):
        """Get a one line summary of commands"""
        commands = ["move <dir>", "eat", "wait", "status", "step", "auto (x to stop)", "stop", "reset", "help", "quit"]
        return " | ".join(commands)             
    
    def process_command(self, command):
        """Execute a command"""
        parts = command.lower().strip().split()
        
        if not parts:
            return
        
        cmd = parts[0]
        
        if cmd == "move":
            if len(parts) < 2:
                print("Usage: move <north/south/east/west>")
                return
            
            direction = parts[1]
            success, message = self.herald.move(direction)
            print(f"→ {message}")
            
            # Check for food after moving
            if success and self.world.has_food_at(self.herald.x, self.herald.y):
                print(f"→ Herald sees food here!")
        
        elif cmd == "eat":
            success, message = self.herald.eat()
            print(f"→ {message}")
        
        elif cmd == "wait":
            self.herald.log_action("WAIT", "Herald waited")
            print("→ Herald does nothing this turn")
        
        elif cmd == "status":
            self.show_detailed_status()
        
        elif cmd == "auto":
            self.auto_mode = True
            print("→ AUTO MODE: Herald will decide on his own")
            print("  (Type 'stop' to take back control)")

        elif cmd == "step":
            self.step_mode = True
            print("→ STEP MODE: Herald will move one tick at a time")
            print("  Press Enter to advance, or 'stop' to exit step mode")
        
        elif cmd == "stop":
            self.auto_mode = False
            self.step_mode = False
            print("→ Manual control resumed")
        
        elif cmd == "reset":
            self.reset_world()
        
        elif cmd == "help":
            self.show_help()
        
        elif cmd == "quit":
            self.running = False
            print("→ Goodbye!")
        
        else:
            print(f"Unknown command: {cmd}")
            print("Type 'help' for commands")
    
    def show_detailed_status(self):
        """Show full Herald info"""
        status = self.herald.get_status()
        print("\n--- HERALD'S STATE ---")
        print(f"Status: {status['status']}")
        print(f"Location: {status['location']}")
        print(f"Hunger: {status['hunger']}/100 ({status['hunger_desc']})")
        print(f"Food at location: {status['sees_food']}")
        
        print("\nRecent actions:")
        for action in self.herald.actions_taken[-5:]:
            print(f"  [{action['timestamp']}] {action['description']}")
        print()

    def show_vision_debug(self):
        """show what herald can see - for debugging"""
        print("\n--- HERALD's VISION DEBUG ---")
        print(f"Herald is at : ({self.herald.x}, {self.herald.y})")
        print(f"Vision rang: 4 squares")
        print("\nAll food on map:")

        food_list = []
        for x in range(self.world.width):
            for y in range(self.world.height):
                if self.world.has_food_at(x, y):
                    distance = abs(x - self.herald.x) + abs(y - self.herald.y)
                    food_list.append((x, y, distance))

        food_list.sort(key=lambda f: f[2])

        for food_x, food_y, distance in food_list:
            visible = "✓ VISIBLE" if distance <= 4 else "x out of range" 
            print(f"    Food at ({food_x}, {food_y}) - Distance: {distance} squares - {visible}")   

        nearest = self.herald.look_around(vision_range=4)
        if nearest:
            print(f"\nHerald's look_around() found: ({nearest[0]}, {nearest[1]})")
        else:
            print(f"\nHerald's look_around() found: NOTHING")
        print()
    
    def herald_auto_decide(self):
        """
        This is where an LLM would go!
        For now, Herald uses simple rules.
        """
        status = self.herald.get_status()

        print(f"[DEBUG] Hunger: {status['hunger']}, Food here: {status['sees_food']}")
        
        # Rule 1: If food here and hungry, eat
        if status['sees_food'] and status['hunger'] > 30:
            print("[Herald thinks: Food right here! I should eat.]")
            self.herald.eat()
            return
        
        # Rule 2: If very hungry, look around for food)
        if status['hunger'] > 40:
            food_location = self.herald.look_around(vision_range=2)
            if food_location:
                food_x, food_y = food_location
                distance = abs(food_x - self.herald.x) + abs(food_y - self.herald.y)
                print(f"[Herald thinks: I see food {distance} squares away! Moving toward it...]")
                self.herald.move_toward(food_x, food_y)
                return
            else:    
                direction = random.choice(["north", "south", "east", "west"])
                print(f"[Herald thinks: I'm hungry, let me search... moving {direction}]")
                self.herald.move(direction)
                return
        
        # Rule 3: If not hungry, explore randomly
        if random.random() < 0.7:  # 70% chance to move
            direction = random.choice(["north", "south", "east", "west"])
            print(f"[Herald thinks: I'll explore {direction}]")
            self.herald.move(direction)
        else:
            print("[Herald thinks: I'll rest here]")
            self.herald.log_action("WAIT", "Herald rested")
    
    def run(self):
        """Main game loop"""
        print("\n" + "="*40)
        print("  HERALD v0.1 - You Are The LLM")
        print("="*40)
        print("\nYou control Herald, an NPC who gets hungry.")
        print("Type 'help' for commands, 'auto' to watch him roam.")
        
        self.show_help()
        
        while self.running and self.herald.alive:
            self.draw_world()
            
            if self.auto_mode:
                print("[AUTO MODE - Herald deciding...(press x + Enter to stop)]")
                if self.check_for_stop_command():
                    self.auto_mode = False
                    print("→ Manual control resumed")
                else:
                    self.herald_auto_decide()
                    time.sleep(1)  # Pause so user can watch
            elif self.step_mode:
                print("\n[STEP MODE - Press Enter to advance, 'stop' to exit]")
                self.show_vision_debug()
    
                command = input(">>> ").strip().lower()
                if command == "stop":
                    self.step_mode = False
                    print("→ Manual control resumed")
                else:
                    # Advance one step
                    self.herald_auto_decide()

        
            else:
                command = input("Your command (or 'help'): ")
                self.process_command(command)
            
            # End of turn - hunger increases
            self.herald.tick()
            self.tick_count += 1
            
            # Check if Herald died
            if not self.herald.alive:
                self.draw_world()
                print("\n💀 HERALD HAS DIED OF STARVATION 💀")
                print(f"He survived {self.tick_count} ticks.")

                choice = input("\nPlay again? (yes/no): ").lower().strip()

                if choice in ['yes', 'y;']:
                    self.reset_world()
                    continue
                else:
                    break
                
        
        print("\nGame Over!")


# Initialize the world and Herald
game = Game()

# Run the game
if __name__ == "__main__":
    game.run()