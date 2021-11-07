import os
import platform
import time
import traceback
from contextlib import closing
from threading import Thread, Lock

import praw
import prawcore
import psycopg2
import schedule

import rep_manager


def catch_exceptions(job_func):
    def wrapper_function(*args, **kwargs):
        global failed_attempt
        try:
            job_func(*args, **kwargs)
            failed_attempt = 1
        except Exception as exp:
            traceback.print_exc()
            # In case of server error pause for multiple of 5 minutes
            if isinstance(exp, (prawcore.exceptions.ServerError, prawcore.exceptions.RequestException)):
                print(f"Waiting {(300 * failed_attempt) / 60} minutes...")
                time.sleep(300 * failed_attempt)
                failed_attempt += 1

            if job_func.__name__ == 'comment_listener':
                raise StopIteration("Reinitialize comment generator")

    return wrapper_function


@catch_exceptions
def submit_rep_transactions():
    print("Hello")
    # TODO: Blah blah


def logger_thread():
    """
    The second thread that runs the logger function to upload everyday rep transactions
    """
    # Run schedule every week at midnight
    schedule.every().day.at("00:00").do(submit_rep_transactions)
    while run_threads:
        schedule.run_pending()
        time.sleep(1)


@catch_exceptions
def comment_listener(comment_stream):
    # Gets a continuous stream of comments
    for comment in comment_stream:
        if comment is None:
            break
        mutex = Lock()
        with mutex:
            rep_manager.load_comment(comment)


def main_thread(*args):
    """
    Thread that runs the main program
    :param args: Argument passed via Thread Module
    """
    # Gets 100 historical comments
    subreddit = args[0].subreddit("MarketMM2")
    comment_stream = subreddit.stream.comments(pause_after=-1, skip_existing=True)
    while run_threads:
        try:
            comment_listener(comment_stream)
        except StopIteration:
            comment_stream = subreddit.stream.comments(pause_after=-1, skip_existing=True)


def main():
    global run_threads

    with closing(psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')) as db_conn:
        with closing(db_conn.cursor()) as cursor:
            cursor.execute("""CREATE TABLE IF NOT EXISTS rep_transactions (comment_id TEXT,
                                                                            comment_created_utc BIGINT,
                                                                            awarder TEXT,
                                                                            awarder_rep INT,
                                                                            awardee TEXT,
                                                                            awardee_rep INT,
                                                                            delta_awardee_rep INT,
                                                                            submission_id TEXT,
                                                                            submission_created_utc BIGINT,
                                                                            permalink TEXT)""")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS comment_ID_index ON rep_transactions (comment_id)")
        db_conn.commit()

    # Logging into Reddit
    reddit = praw.Reddit(client_id=os.getenv("client_id"),
                         client_secret=os.getenv("client_secret"),
                         username=os.getenv("reddit_username"),
                         password=os.getenv("reddit_password"),
                         user_agent=f"{platform.platform()}:MarketMM2Rep:1.0 (by u/is_fake_Account)")
    print(f"Account u/{reddit.user.me()} Logged In...")
    # Create threads
    main_thread_handler = Thread(target=main_thread, args=(reddit,))
    logger_thread_handler = Thread(target=logger_thread)
    try:
        # run the threads
        main_thread_handler.start()
        logger_thread_handler.start()
        print("Bot has now started!", time.strftime('%I:%M %p %Z'))
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        run_threads = False
        main_thread_handler.join()
        logger_thread_handler.join()
        print("Bot has stopped!", time.strftime('%I:%M %p %Z'))
        quit()


if __name__ == '__main__':
    run_threads = True
    failed_attempt = 1
    main()
