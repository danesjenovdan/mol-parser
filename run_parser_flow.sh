#!/bin/bash
echo "parse speeches, votes, questions"
scrapy crawl sessions
echo "parse committee sessions"
scrapy crawl committee_sessions
cd /app
echo "start setting votes results"
python manage.py set_votes_result --majority relative_normal
echo "start setting motion tags"
python manage.py set_motion_tags
echo "start pairing votes with speeches"
python manage.py pair_votes_and_speeches
echo "lematize speeches"
python manage.py lemmatize_speeches
echo "set tfidf"
python manage.py set_tfidf_for_sessions
echo "run analysis for today"
python manage.py daily_update
echo "send notifications"
python manage.py send_daily_notifications
