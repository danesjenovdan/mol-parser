#!/bin/bash
echo "pasre sessions"
scrapy crawl sessions
cd /app
echo "set tfidf"
python manage.py set_tfidf
echo "start setting votes results"
python manage.py set_votes_result --majority relative_normal
echo "start setting motion tags"
python manage.py set_motion_tags
echo "start pairing votes with speeches"
python manage.py pair_votes_and_speeches
echo "send notifications"
python manage.py send_daily_notifications
