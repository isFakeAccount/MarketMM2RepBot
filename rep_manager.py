import os
import re
from contextlib import closing

import psycopg2

import CONSTANTS
import bot_responses
import flair_functions


def is_mod(redditor) -> bool:
    """
    Checks if the author is moderator or not

    :param redditor: The reddit account instance
    :return: True if author is moderator otherwise False
    """
    moderators_list = redditor._reddit.subreddit("MarketMM2").moderator()
    if redditor in moderators_list:
        return True
    else:
        return False


def close_command(comment):
    """
    Performs checks if the submission can be closed

    :param comment: The comment object praw
    """
    # Only OP can close the trade
    if comment.author == comment.submission.author or is_mod(comment.submission.author):
        # You can close trading posts only
        if comment.submission.link_flair_text == 'Trade Offer':
            flair_functions.mark_submission_as_closed(comment.submission)
            bot_responses.close_submission_comment(comment)
        else:
            # If post isn't trading post
            bot_responses.close_submission_failed(comment, False)
    else:
        # If the close submission is requested by someone other than op and mod
        bot_responses.close_submission_failed(comment, True)


def load_comment(comment):
    """
    Loads the comment and if it a command, it executes the respective function

    :param comment: comment that is going to be checked
    """
    if comment.author.name == "AutoModerator":
        return None

    # De-Escaping for fancy pants editor
    comment_body = comment.body.replace('\\', '')
    if re.match(CONSTANTS.REP_PLUS, comment_body, re.I):
        pass
    elif re.match(CONSTANTS.CLOSE, comment_body, re.I):
        close_command(comment)
    elif re.match(CONSTANTS.REP_MINUS, comment_body, re.I):
        if is_mod(comment.author):
            flair_functions.decrement_rep(comment)
            with closing(psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')) as db_conn:
                with closing(db_conn.cursor()) as cursor:
                    comment.refresh()
                    cursor.execute("INSERT INTO rep_transactions VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                   (comment.id,
                                    comment.created_utc,
                                    comment.author.name,
                                    comment.author_flair_text.split()[-1],
                                    comment.parent().author.name,
                                    comment.parent().author_flair_text.split()[-1],
                                    -1,
                                    comment.submission.id,
                                    comment.submission.created_utc,
                                    comment.permalink)
                                   )
                db_conn.commit()

            bot_responses.rep_subtract_comment(comment)
