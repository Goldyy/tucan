#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import argparse
import json
import mechanize
import telegram
import configparser
from netrc import netrc
from hashlib import md5
from lxml import html


def mail(recipient, subject, body):
    import subprocess

    proc = subprocess.Popen(["mail", "-s", subject, recipient],
                            stdin=subprocess.PIPE)
    proc.stdin.write(body.encode('utf-8'))
    proc.stdin.close()

def send_telegram_bot_notification():
    config = configparser.ConfigParser()
    config.read(os.path.expanduser('~/.tucan_telegram'))

    bot = telegram.Bot(token=config['Telegram']['token'])
    bot.send_message(chat_id=config['Telegram']['chat'], 
        text='Hi, please check Tucan, new grades are available! \nRegards, your Bot')


def parse_netrc():
    username, _, password = netrc().authenticators("www.tucan.tu-darmstadt.de")
    return username, password


def update_db(db, grades):
    if os.path.isfile(db):
        with open(db) as db_fp:
            old_digests = set(db_fp.read().split(os.linesep))
    else:
        old_digests = set()

    new_digests = {md5(repr(g)).hexdigest(): g for g in grades}

    if set(new_digests.keys()) != old_digests:
        with open(db, "w") as db_fp:
            db_fp.write(os.linesep.join(old_digests.union(new_digests.keys())))

        return [v for k, v in new_digests.items() if k not in old_digests]

    return None

def get_grades(username, password):
    br = mechanize.Browser()

    # Changes by: https://github.com/nyorain/tucan
    br.addheaders = [('User-agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.146 Safari/537.36')]
    br.set_handle_robots(False)
    br.set_handle_refresh(True)
    br.set_handle_redirect(True)
    br.set_handle_equiv(False)

    br.open("https://www.tucan.tu-darmstadt.de/scripts/mgrqispi.dll?APPNAME=CampusNet&PRGNAME=EXTERNALPAGES&ARGUMENTS=-N000000000000001,-N000344,-Awelcome")
    br.select_form(nr=0)
    br.form["usrname"] = username
    br.form["pass"] = password
    br.submit()

    br.follow_link(text_regex=u"^Startseite$")
    br.follow_link(text="Prüfungen")
    br.follow_link(text="Semesterergebnisse")
    br.follow_link(text="Prüfungsergebnisse")

    tree = html.fromstring(br.response().read())
    tbody = tree.xpath("//table[@class='nb list']/tbody")[0]

    grades = [[" ".join(unicode(td.text).strip().split())
               for td in tr.findall("td")][:-1]
              for tr in tbody.findall("tr")]
    return grades

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TUCaN CLI",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--mail", "-m", type=str,
                        help="send email to this address on changes")
    parser.add_argument("--db", type=str,
                        default=os.path.expanduser("~/.tucandb"),
                        help="database file")
    parser.add_argument("--new", help="print only new grades", action="store_true")
    parser.add_argument("--json", "-j", help="output json", action="store_true")
    parser.add_argument("--telegram-notification", 
                        dest="telegram",
                        help="Send a notification to telegram chat configured in file ~/.tucan_telegram",
                        action="store_true")
    args = parser.parse_args()

    username, password = parse_netrc()
    grades = get_grades(username, password)

    if args.mail or args.new:
        new_grades = update_db(args.db, grades)

        if new_grades:
            msg = os.linesep.join([g[0] + ": " + g[2] for g in new_grades])
            if args.mail:
                mail(args.mail, "New Grade in TUCaN", msg)
            if args.telegram:
                send_telegram_bot_notification()
            else:
                print(msg)
    else:
        if args.json:
            print(json.dumps(list(grades)))
        else:
            for grade in grades:
                print(grade[0] + ": " + grade[2])
