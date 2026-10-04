import sys

if "--live" in sys.argv:
    from bestthemes_win.live_player import main
else:
    from bestthemes_win.app import main

sys.exit(main())
