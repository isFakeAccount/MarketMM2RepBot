import CONSTANTS


def mark_submission_as_closed(submission):
    """
    Changes the flair of submission to Traded Ended and locks the comments.

    :param submission: The submission whose flair will be changed.
    """
    submission.flair.select(CONSTANTS.TRADE_ENDED_FLAIR_ID)
    submission.mod.lock()


def decrement_rep(comment):
    """
    Decrements the user flair by one of the parent comment/submission author.

    :param comment: The comment that triggered the command. Parent of this will be considered.
    """
    parent_post = comment.parent()
    author_name = parent_post.author.name

    marketmm2 = comment._reddit.subreddit("MarketMM2")
    # if the author has no flair
    if not parent_post.author_flair_css_class:
        marketmm2.flair.set(author_name, text='Trade Rep: -1', flair_template_id=CONSTANTS.REP_FLAIR_ID)
    else:
        # Getting the flair and adding the value
        user_flair = parent_post.author_flair_text

        # Splits rep into two
        user_flair_split = user_flair.split()
        user_flair_split[-1] = int(user_flair_split[-1])
        user_flair_split[-1] -= 1
        # Combines back string and int part
        user_flair = ' '.join(map(str, user_flair_split))
        marketmm2.flair.set(author_name, text=user_flair, flair_template_id=parent_post.author_flair_template_id)


def increment_rep(comment):
    """
    Increments the user flair by one of the parent comment/submission author.

    :param comment: The comment that triggered the command. Parent of this will be considered.
    """
    parent_post = comment.parent()
    author_name = parent_post.author.name

    marketmm2 = comment._reddit.subreddit("MarketMM2")
    # if the author has no flair
    if not parent_post.author_flair_css_class:
        marketmm2.flair.set(author_name, text='Trade Rep: 1', flair_template_id=CONSTANTS.REP_FLAIR_ID)
    else:
        # Getting the flair and adding the value
        user_flair = parent_post.author_flair_text

        # Splits rep into two
        user_flair_split = user_flair.split()
        user_flair_split[-1] = int(user_flair_split[-1])
        user_flair_split[-1] += 1
        # Combines back string and int part
        user_flair = ' '.join(map(str, user_flair_split))
        marketmm2.flair.set(author_name, text=user_flair, flair_template_id=parent_post.author_flair_template_id)
