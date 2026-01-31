# Test OpenWISP QA Commands

This PR tests the new OpenWISP QA integration in the CI failure bot.

The bot should now recommend:
- `pip install -e .[qa]`
- `./run-qa-checks`
- `openwisp-qa-format`

The file `qa_violation_test.py` contains intentional formatting violations to trigger the bot.