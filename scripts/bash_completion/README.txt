To enable bash completion for lazyrunner, copy lazyrunner_completion
into /etc/bash_completion.d/. Tab completion should then be available
after restarting bash or running 

$ source /etc/bash_completion

Alternatively, add the following to your .bashrc init script:

$ source <lazyrunner_source_dir>/scripts/bash_completion/lazyrunner_completion

For speed, completion works on cached preset names.  Anytime Z is run
(except for just printing the help message), this cache is regenerated.
