#!/bin/bash

tmux new -d -s sh 
tmux new -d -s jn 
tmux new -d -s gh
tmux new -d -s top htop
tmux new -d -s py python3
tmux new -d -s r R
sleep 3s
tmux send-keys -t gh C-z 'cd ~/Src_SOMOSPIE && git status' Enter
tmux send-keys -t jn C-z 'ezj -q' Enter
tmux send-keys -t sh C-z 'cd ~/Src_SOMOSPIE/code && ls' Enter
tmux ls

