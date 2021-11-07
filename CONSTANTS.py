from enum import Enum

# Regex for the commands
REP_PLUS = r"(\++REP|REP\++)"
REP_MINUS = r"(-+REP|REP-+)"
CLOSE = r"(!CLOSE|CLOSE!)"

# User Flairs
REP_FLAIR_ID = '13e6e140-2b0c-11ec-8a70-0a847492ab37'

# Submission Flair
TRADE_ENDED_FLAIR_ID = '50796ea6-3ecc-11ec-92ff-6eae3c530754'


class StatusCodes(Enum):
    CHECKS_PASSED = 0
    CANNOT_REWARD_YOURSELF = 1
    MORE_THAN_TWO_USERS = 2
    CANNOT_REWARD_SUBMISSION = 3
    INCORRECT_SUBMISSION_TYPE = 4
    COOL_DOWN_TIMER = 5
    KARMA_AWARDING_LIMIT_REACHED = 6
    DELETED_OR_REMOVED = 7
