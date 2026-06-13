import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))
from agent_2_editor import generate_headline

title = "Rita Wilson on Her 38-Year Marriage to Tom Hanks, Surviving Cancer & Her 'Deeply Personal' Music"
print("Generated:", generate_headline(title))
