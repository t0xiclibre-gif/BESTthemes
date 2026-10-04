import sys

if "--live" in sys.argv:
    # Lecteur du fond d'écran animé (processus séparé, lancé par BESTthemes ou à la connexion)
    from .live_player import main
else:
    from .main import main

sys.exit(main())
