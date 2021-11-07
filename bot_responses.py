import praw
import prawcore
import yaml


def reply(comment_or_submission, body):
    response = body + "\n\n^(This action was performed by a bot, please contact the mods for any questions.)"
    try:
        new_comment = comment_or_submission.reply(response)
        new_comment.mod.distinguish(how="yes")
        new_comment.mod.lock()
    except prawcore.exceptions.Forbidden:
        raise prawcore.exceptions.Forbidden("Could not distinguish/lock comment")
    except praw.exceptions.APIException:
        new_comment = comment_or_submission.submission.reply(response)
        new_comment.mod.distinguish(how="yes")
        new_comment.mod.lock()


def get_comment_from_config(comment, config_name):
    """
    Gets the comment body from the wiki config

    :param comment: Comment that triggered that command
    :param config_name: The config document name that will be used.
    :return: comment body from config document
    """
    comment_body = "Something went wrong, please contact mods asap."
    config = comment._reddit.subreddit("MarketMM2").wiki['marketmm2botsconfig/rep_bot_config'].content_md
    for config in yaml.safe_load_all(config):
        if config['type'] == config_name:
            comment_body = config['comment']
            comment_body = comment_body.replace('{{author}}', comment.author.name)
            comment_body = comment_body.replace('{{parent-author}}', comment.parent().author.name)
            return comment_body
    return comment_body


def close_submission_comment(comment):
    """
    Replies with the comment for letting user know that the submission has been closed
    :param comment: The comment that triggered the command and will be replied to.
    """
    comment_body = get_comment_from_config(comment, 'submission_closed_successfully')
    reply(comment, comment_body)


def close_submission_failed(comment, is_trading_post):
    """
    Replies with the comment for letting user know that the submission closing was not successful.
    :param is_trading_post:
    :param comment: The comment that triggered the command and will be replied to.
    """
    if not is_trading_post:
        comment_body = get_comment_from_config(comment, 'submission_closed_failed_not_op_or_mod')
    else:
        comment_body = get_comment_from_config(comment, 'submission_closed_not_trading_post')
    reply(comment, comment_body)


def rep_subtract_comment(comment):
    """
    Replies with the comment for letting user know that the rep has been subtracted successfully.
    :param comment: The comment that triggered the command and will be replied to.
    """
    comment_body = get_comment_from_config(comment, 'subtract_rep_successful')
    reply(comment, comment_body)
