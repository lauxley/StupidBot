SCREEN_NAME=ircbot

source env/bin/activate
screen -wipe
screen_nb=`screen -ls | grep $SCREEN_NAME | wc -l`
if [ $screen_nb -gt 0 ]
then
echo "killing existing $SCREEN_NAME"
screen -X -S $SCREEN_NAME quit
sleep 5
fi

screen -dmS ircbot python NotABot.py