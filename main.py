import csv
import io
import json
import os
import platform
import time
import traceback
from contextlib import closing
from datetime import datetime
from pprint import pprint
from threading import Thread, Lock

import praw
import prawcore
import psycopg2
import requests
import schedule

import rep_manager


def send_message_to_discord(msg, webhook):
    """
    Sends the message to discord channel via webhook url.
    :param webhook: URL of channel webhook where the message will be posted.
    :param msg: message content.
    """
    data = {"content": msg, "username": "Karma Bot"}
    output = requests.post(os.getenv(webhook), data=json.dumps(data), headers={"Content-Type": "application/json"})
    try:
        output.raise_for_status()
    except requests.HTTPError:
        pprint(msg)


def catch_exceptions(job_func):
    def wrapper_function(*args, **kwargs):
        global failed_attempt
        try:
            job_func(*args, **kwargs)
            failed_attempt = 1
        except Exception as exp:
            send_message_to_discord(traceback.format_exc(), 'error_msg_channel')
            # In case of server error pause for multiple of 5 minutes
            if isinstance(exp, (prawcore.exceptions.ServerError, prawcore.exceptions.RequestException)):
                print(f"Waiting {(300 * failed_attempt) / 60} minutes...")
                time.sleep(300 * failed_attempt)
                failed_attempt += 1

            if job_func.__name__ == 'comment_listener':
                raise StopIteration("Reinitialize comment generator")

    return wrapper_function


@catch_exceptions
def delete_old_rep_transactions():
    """
    Deletes the rep logs older than 6 months.
    """
    seconds_in_six_months = 180 * 60 * 60 * 24
    unix_time_now = time.time()
    unix_time_six_months_ago = unix_time_now - seconds_in_six_months
    mutex = Lock()
    with mutex:
        with closing(psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')) as db_conn:
            with closing(db_conn.cursor()) as cursor:
                cursor.execute(f"DELETE FROM rep_transactions WHERE submission_created_utc <= '{int(unix_time_six_months_ago)}'")
            db_conn.commit()

    with mutex:
        with closing(psycopg2.connect(os.getenv('DATABASE_URL'), sslmode='require')) as db_conn:
            with closing(db_conn.cursor()) as cursor:
                cursor.execute(f"SELECT * FROM rep_transactions WHERE comment_created_utc >= '{int(time.time() - 86400)}'")
                results = cursor.fetchall()
                with closing(io.StringIO()) as str_buffer:
                    csv_writer = csv.writer(str_buffer)
                    csv_writer.writerow(['comment_id',
                                         'comment_created_utc',
                                         'awarder,awarder_rep',
                                         'awardee,awardee_rep',
                                         'delta_awardee_rep',
                                         'submission_id',
                                         'submission_created_utc',
                                         'permalink'])
                    csv_writer.writerows(results)

                    # Logging into Reddit
                    reddit = praw.Reddit(client_id=os.getenv("client_id"),
                                         client_secret=os.getenv("client_secret"),
                                         username=os.getenv("reddit_username"),
                                         password=os.getenv("reddit_password"),
                                         user_agent=f"{platform.platform()}:MarketMM2Rep:1.0 (by u/is_fake_Account)")
                    reddit.validate_on_submit = True
                    profile_subreddit = reddit.subreddit(f"u_{os.getenv('reddit_username')}")
                    submission = profile_subreddit.submit(title=f"Rep Logs {datetime.now().isoformat()}", selftext=str_buffer.getvalue())
                    send_message_to_discord(f"Rep logs for the day https://www.reddit.com{submission.permalink}", 'rep_updates_channel')


def db_manager_thread():
    """
    The second thread that runs the logger function to upload everyday rep transactions.
    """
    # Run schedule every week at midnight
    schedule.every().day.at("00:00").do(delete_old_rep_transactions)
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
    Thread that runs the main program.

    :param args: Argument passed via Thread Module.
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
    reddit.validate_on_submit = True
    # Create threads
    main_thread_handler = Thread(target=main_thread, args=(reddit,))
    db_manager_thread_handler = Thread(target=db_manager_thread)
    try:
        # run the threads
        main_thread_handler.start()
        db_manager_thread_handler.start()
        print("Bot has now started!", time.strftime('%I:%M %p %Z'))
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        run_threads = False
        main_thread_handler.join()
        db_manager_thread_handler.join()
        print("Bot has stopped!", time.strftime('%I:%M %p %Z'))
        quit()


if __name__ == '__main__':
    run_threads = True
    failed_attempt = 1
    main()
