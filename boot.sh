BASE_SCREEN_NAME=ircbot
if [ $# -gt 0 ]
then
    SUFFIX=`echo $1 | sed 's/\(.*\)\..*/\1/'`
    SCREEN_NAME=$BASE_SCREEN_NAME$SUFFIX
else
    SCREEN_NAME=$BASE_SCREEN_NAME
fi

echo "launching $SCREEN_NAME.."

source env/bin/activate
screen -wipe
screen_nb=`screen -ls | grep $SCREEN_NAME | wc -l`
if [ $screen_nb -gt 0 ]
then
    echo "killing existing $SCREEN_NAME"
    screen -X -S $SCREEN_NAME quit
    sleep 5
fi

screen -dmS $SCREEN_NAME python NotABot.py

echo 'done.'