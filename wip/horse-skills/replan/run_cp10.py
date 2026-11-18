import sys; sys.path.insert(0, "/home/claude/bdo-tools/wip/horse-skills/replan")
import replan2 as R
R.SETTINGS.update({"checkpoints": [int(sys.argv[3])]})
sys.argv = ["replan2.py", sys.argv[1], "--horses", sys.argv[2]]
R.main()
