import os
import re
import time
from contextlib import closing

import psycopg2
import yaml

import CONSTANTS
import bot_responses
import flair_functions
from CONSTANTS import StatusCodes


def is_mod(redditor) -> bool:
    """
    Checks if the author is moderator or not.

    :param redditor: The reddit account instance.
    :return: True if author is moderator otherwise False.
    """
    moderators_list = redditor._reddit.subreddit("MarketMM2").moderator()
    if redditor in moderators_list:
        return True
    else:
        return False


def is_removed_or_deleted(content) -> bool:
    """
    Checks if comment, parent comment or submission has been removed/deleted. If it is deleted, the author is None.
    If it is removed, the removed_by will have moderator name.
    :param content: Reddit comment or submission
    :return: True if the items is deleted or removed. Otherwise, False.
    """
    return content.author is None or content.mod_note or content.removed


def get_limits_from_config(limit_type, comment):
    config = comment._reddit.subreddit("MarketMM2").wiki['marketmm2botsconfig/rep_bot_config'].content_md
    for config in yaml.safe_load_all(config):
        if config['type'] == 'limits':
            return config[limit_type]
    raise KeyError(f"{limit_type} Config not found")


def close_command(comment):
    """
    Performs checks if the submission can be closed.

    :param comment: The comment object praw.
    """
    # Only OP can close the trade
    if comment.author == comment.submission.author or is_mod(comment.submission.author):
        # You can close trading posts only
        if re.match(r"Trade\sOffer|Giveaway\sEntry", comment.submission.link_flair_text):
            flair_functions.mark_submission_as_closed(comment.submission)
            bot_responses.close_submission_comment(comment)
        else:
            # If post isn't trading post
            bot_responses.close_submission_failed(comment, True)
    else:
        # If the close submission is requested by someone other than op and mod
        bot_responses.close_submission_failed(comment, False)


def increase_rep(comment):
    flair_functions.increment_rep(comment)
    with closing(psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')) as db_conn:
        with closing(db_conn.cursor()) as cursor:
            marketmm2 = comment._reddit.subreddit("MarketMM2")
            # If the user has no flair, assigns them flair. However since the flair takes time to apply
            # .author_flair_text.split() will still throw an exception, hence it is manually set to zero
            if not comment.author_flair_css_class:
                marketmm2.flair.set(comment.author.name, text='Trade Rep: 0', flair_template_id=CONSTANTS.REP_FLAIR_ID)
                awarder_rep = 0
            else:
                awarder_rep = comment.author_flair_text.split()[-1]

            if not comment.parent().author_flair_css_class:
                marketmm2.flair.set(comment.parent().author.name, text='Trade Rep: 0',
                                    flair_template_id=CONSTANTS.REP_FLAIR_ID)
                awardee_rep = 0
            else:
                awardee_rep = comment.parent().author_flair_text.split()[-1]

            comment.refresh()
            cursor.execute("INSERT INTO rep_transactions VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                           (comment.id,
                            comment.created_utc,
                            comment.author.name,
                            awarder_rep,
                            comment.parent().author.name,
                            awardee_rep,
                            1,
                            comment.submission.id,
                            comment.submission.created_utc,
                            comment.permalink)
                           )
        db_conn.commit()
        bot_responses.rep_rewarded_comment(comment)


def checks_for_rep_command(comment):
    if not re.match(r"Trade\sOffer|Giveaway\sEntry", comment.submission.link_flair_text):
        bot_responses.incorrect_submission_type_comment(comment)
        return StatusCodes.INCORRECT_SUBMISSION_TYPE

    # Make sure author isn't rewarding themselves
    if comment.author == comment.parent().author:
        bot_responses.cannot_reward_yourself_comment(comment)
        return StatusCodes.CANNOT_REWARD_YOURSELF

    # If comment itself or the submission has been removed/deleted
    removed_or_deleted = [comment, comment.parent(), comment.submission]
    if any(map(is_removed_or_deleted, removed_or_deleted)):
        bot_responses.deleted_or_removed_comment(comment)
        return StatusCodes.DELETED_OR_REMOVED

    with closing(psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')) as db_conn:
        with closing(db_conn.cursor()) as cursor:
            # Checking if user has not cross the general rep limit for the day
            seconds_from_previous_midnight = time.localtime().tm_hour * 3600 + time.localtime().tm_min * 60 + time.localtime().tm_sec
            unix_time_at_previous_midnight = time.time() - seconds_from_previous_midnight
            cursor.execute("SELECT COUNT(*) FROM rep_transactions WHERE awarder=%s AND comment_created_utc>=%s",
                           (comment.author.name, unix_time_at_previous_midnight))
            count = cursor.fetchone()[0]
            if count >= get_limits_from_config('rep_limit_per_day', comment):
                bot_responses.reward_limit_reached_comment(comment)
                return StatusCodes.REP_AWARDING_LIMIT_REACHED

            # checking if user is trying to give rep to same user before rep cooldown expires
            unix_time_30_min_ago = time.time() - get_limits_from_config('rep_cooldown', comment) * 60
            cursor.execute("SELECT COUNT(*) FROM rep_transactions WHERE awarder=%s AND awardee=%s AND comment_created_utc>=%s",
                           (comment.author.name, comment.parent().author.name, unix_time_30_min_ago))
            count = cursor.fetchone()[0]
            if count >= 1:
                bot_responses.cooldown_timer_reached_comment(comment)
                return StatusCodes.COOL_DOWN_TIMER

            if 'giveaway' in comment.submission.link_flair_text.lower():
                # Checking how many rep has been awarded to the parent comment author on this giveaway submission.
                cursor.execute("SELECT COUNT(*) FROM rep_transactions WHERE awardee=%s AND submission_id=%s",
                               (comment.parent().author.name, comment.submission.id))
                count = cursor.fetchone()[0]
                # If limit is exceeded the rep is not rewarded.
                if count >= get_limits_from_config('giveaway_rep_limit_per_post', comment):
                    bot_responses.giveway_limit_reached(comment)
                    return StatusCodes.GIVEAWAY_LIMIT

    return StatusCodes.CHECKS_PASSED


def process_rep_command(comment):
    if checks_for_rep_command(comment) == StatusCodes.CHECKS_PASSED:
        increase_rep(comment)


def load_comment(comment):
    """
    Loads the comment and if it is a command, it executes the respective function.

    :param comment: comment that is going to be checked.
    """
    if comment.author.name == "AutoModerator":
        return None

    # De-Escaping for fancy pants editor
    comment_body = comment.body.replace('\\', '')
    if re.match(CONSTANTS.REP_PLUS, comment_body, re.I):
        if is_mod(comment.author):
            increase_rep(comment)
        else:
            process_rep_command(comment)

    elif re.match(CONSTANTS.CLOSE, comment_body, re.I):
        close_command(comment)
    elif re.match(CONSTANTS.REP_MINUS, comment_body, re.I):
        if is_mod(comment.author):
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
            flair_functions.decrement_rep(comment)
            bot_responses.rep_subtract_comment(comment)
    elif re.match(CONSTANTS.MOD, comment_body, re.I):
        if re.match(r"Trade\sOffer|Giveaway\sEntry", comment.submission.link_flair_text):
            mod_list = []
            for moderator in comment._reddit.subreddit("MarketMM2").moderator():
                if moderator.name != 'mm2repbot':
                    mod_list.append(f"u/{moderator.name}")
            bot_responses.mods_request_comment(comment, mod_list)
    elif regex_match := re.match(CONSTANTS.REP_LOGS, comment_body, re.I):
        if is_mod(comment.author):
            author_name = regex_match.group(1)
            days = regex_match.group(2)
            try:
                redditor = comment._reddit.Redditor(author_name).name
            except AttributeError:
                print("EEEEEEEEEEEEEEEEE")
