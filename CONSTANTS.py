from enum import Enum

# Regex for the commands
REP_PLUS = r"(\++REP|REP\++)"
REP_MINUS = r"(-+REP|REP-+)"
CLOSE = r"(!CLOSE|CLOSE!)"
MOD = r"(!MOD|MOD!)"

# User Flairs
REP_FLAIR_ID = '13e6e140-2b0c-11ec-8a70-0a847492ab37'

# Submission Flair
TRADE_ENDED_FLAIR_ID = '50796ea6-3ecc-11ec-92ff-6eae3c530754'


class StatusCodes(Enum):
    CHECKS_PASSED = 0
    CANNOT_REWARD_YOURSELF = 1
    INCORRECT_SUBMISSION_TYPE = 2
    COOL_DOWN_TIMER = 3
    REP_AWARDING_LIMIT_REACHED = 4
    DELETED_OR_REMOVED = 5
