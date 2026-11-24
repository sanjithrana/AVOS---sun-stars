"""The 29 skills the kits add, in three groups. One implementation (skill.py) serves them all; only the entries below differ."""
from __future__ import annotations

G_STORY, G_ANIM, G_3D = "Kits · Story engines", "Kits · Animation styles", "Kits · 3D styles"

STORY = {
    "cartoon": dict(name="Cartoon Shorts", dir="cartoon", about="Chunky 3D cartoon characters, camera moves and sound effects, built from one narration. The classic kit: a script becomes a funny 40-second short.",
                    examples=["The Pig War: two empires nearly fought over one pig", "The Great Emu War of 1932", "Why the Mona Lisa vanished"]),
    "cartoon3d": dict(name="Cartoon Shorts 3D+2D", dir="cartoon3d", about="The upgraded Cartoon Shorts: 3D worlds with 2D painted cards, richer rooms, a bigger sample library and a story-formula guide.",
                      examples=["Napoleon and the rabbit army", "The pig war", "A bakery that sold a wrong cake"]),
    "science": dict(name="Science Story Shorts", dir="science", about="True science and history stories told as 3D cartoons: a hook, the problem, the twist, the payoff. Facts are kept straight.",
                    examples=["The clock that saved sailors", "The map nobody believed", "The cows that sprouted grass"]),
    "stickman": dict(name="Stickman Shorts", dir="stickman", about="Hand-drawn stickman stories with exact word timing, big poses, doodle props and a comic sound track.",
                     examples=["Why the ocean is salty", "Why onions make you cry", "What is inside a black hole"]),
}

# slug -> (name, one-line look, best for)
ANIM = {
    "stickman": ("Stickman", "Black ink lines on white paper, circle heads, big poses; the joke is in the timing", "jokes, how-things-work, quick stories"),
    "claymation": ("Claymation", "Plasticine stop-motion in real 3D, thumbprints, a little diorama", "kids' stories, food, nature"),
    "anime-watercolor": ("Anime Watercolor", "Hand-painted anime sky, cumulus clouds, watercolour washes", "calm stories, travel, poems"),
    "ascii-art": ("ASCII Art", "The whole picture typed in characters on a dark terminal", "tech, hacking, code, retro"),
    "paper-cutout": ("Paper Cut-out", "A pop-up book of coloured paper with real shadows", "history, fairy tales, kids"),
    "kurzgesagt": ("Kurzgesagt style", "Bold flat vector, gradients and glow, deep space colours", "science, space, biology"),
    "ink-wash": ("Ink Wash", "Sumi-e brush painting: black ink, mist, one red seal", "philosophy, nature, Asia"),
    "voxel-art": ("Voxel Art", "A world of cubes with tiny textures, raised camera", "games, building, maps"),
    "1930s-cartoon": ("1930s Cartoon", "Rubber-hose animation on old film with grain and flicker", "comedy, nostalgia, music"),
    "3d-movie": ("3D Movie style", "Glossy toy-like materials, soft reflections, cinematic camera", "products, stories, trailers"),
}

STYLES3D = {
    "toy-diorama": ("Toy Diorama", "a toy world on a floating slab of land, drone camera", "journeys, supply chains, step-by-step places"),
    "soft-clay": ("Soft Clay", "plasticine stop-motion on a paper sweep", "growth, nature, kids' science, cooking"),
    "low-poly": ("Low-Poly", "a faceted world, triangle sea, gem clouds", "weather, nature processes, landscapes"),
    "paper-layers": ("Paper Layers", "a cut-paper shadow box with soft layered shadows", "light, colour, nature, picture-book stories"),
    "inflatable": ("Inflatable", "glossy balloon objects that inflate and bounce", "energy, filling up, friendly tech"),
    "glass-lab": ("Glass Lab", "lab glass and coloured liquids in a studio", "chemistry, density, mixing, measuring"),
    "neon-night": ("Neon Night", "synthwave grid, neon outlines, bloom", "internet, signals, gaming, security"),
    "blueprint": ("Blueprint Build", "a drawing plots on blueprint paper, then stands up into a model", "engineering, structures, plans to objects"),
    "voxel": ("Voxel Build", "cubes drop in and build up on a plinth", "growth over time, building, maps"),
    "exploded-view": ("Exploded View", "a product comes apart with numbered callouts", "what's inside a device, parts"),
    "particles": ("Particle Swarm", "36,000 glowing points morph between shapes", "AI, data, ideas, transformations"),
    "data-towers": ("Data Towers", "a bar chart as an architect's model", "real numbers, growth, comparisons"),
    "studio-product": ("Studio Product", "a dark studio, mirror floor, strip lights", "product reveals and launches"),
    "toon-ink": ("Toon Ink", "cel shading, ink outlines, comic captions", "action, space, history, kids"),
    "floating-screens": ("Floating Screens", "app screens as glass cards with rack focus", "apps, websites, user flows"),
}
PREFIX = "kit-"
