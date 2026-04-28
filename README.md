System Defender

Course: CSE423: Computer Graphics (Spring 2026)   
 
💻 Project Description

System Defender is an interactive 3D survival shooter developed using PyOpenGL, building upon the foundational mechanics of our Assignment 3 template. The game immerses the player inside a corrupted computer motherboard, where they control an "Antivirus Tank" tasked with neutralizing hostile "Malware Bugs".  

Our project heavily utilizes hierarchical modeling, dynamic environmental interactions, and vector-based physics. We also utilize depth testing (GL_DEPTH_TEST) to ensure accurate 3D spatial visualization.  
🚀 Key Features & Division of Labor

Tanjila Afsari Rubina

    Independent Turret Mechanics (Hierarchical Modeling): Segmented the player model into a mobile base and an independent turret, utilizing advanced matrix stack management (glPushMatrix() and glPopMatrix()) for independent aiming.  

    Dynamic "Firewall" Obstacles: Programmed vertical cuboids as environmental cover that continuously rise and fall from the grid floor using trigonometric sine functions.  

    Tactical Drone Camera (Dynamic Projection): Implemented a top-down orthographic/perspective hybrid view using gluLookAt() for tactical routing.  

    Level-Based Progression System: Created a dynamic difficulty system that scales enemy spawn rates and alters grid colors based on the player's score.  

    The "Mother-Bug" Boss Entity: Developed a high-health boss variant that conditionally shrinks in size (glScalef()) upon registering projectile collisions.  

    Reactive HUD & Scoring System: Built a 2D orthographic text overlay that actively reads player health, altering RGB values (e.g., green for full, flashing red for critical) to provide real-time feedback.  

Sandip Kumar Paul

    Parabolic Bomb Mechanics (Projectile Physics): Engineered bomb projectiles using kinematic equations to simulate gravity and a 3D parabolic trajectory.  

    Particle Explosion Physics: Created a dynamic particle system where destroyed enemies instantiate smaller primitive shapes that translate outward along randomized directional vectors.  

    Adaptive Malware Algorithms (Complex Kinematics): Programmed evolving enemy AI, shifting from linear tracking in early levels to complex vector-based homing and trigonometric evasive maneuvers later on.  

    Hovering Power-Ups: Implemented randomized, collectible items utilizing continuous rotation (glRotatef()) and slight vertical oscillation (glTranslatef()) via distance-based collision detection.  

    Spherical Ricochet Physics (Boundary Reflection): Modeled projectiles using gluSphere() that interact with the physical bounds of the arena, inverting X or Y velocity vectors upon wall intersections.  

    Interactive Grid Zones (Buffs & Debuffs): Assigned specific mathematical quadrants on the floor as active status zones, applying movement penalties (Corrupted zones) or health boosts (Secure zones) upon player intersection.  

⚙️ Technologies Used

    Language: Python

    Graphics Library: PyOpenGL (GLUT, GLU, GL)
