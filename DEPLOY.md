# Deployment process

## Preparations

### Check buildbot

Make sure everything is green: <http://buildbot.openend.se:8080/waterfall>


### Test deploy

    cd /src/accounting
    fab -f misc/fabfile.py deploy_staging


### Kill any automatic rebuild scripts

If you're running `make watch` or similar, stop it.


### Merge to deployment branch

    cd /src/accounting
    hg pull
    hg up deploy
    hg merge default
    hg ci -m 'merge for deploy'
    hg up default
    cd /src/accounting-client
    hg pull
    hg up deploy
    hg merge default
    hg ci -m 'merge for deploy'
    hg up default


## Live deploy

    cd /src/accounting
    fab -f misc/fabfile.py deploy_live

Log in to any machine and run

    PYTHONPATH=/root/accounting /root/accounting/bin/upgrade.py


## Post deployments


### Check live system

Log in to the live system and check that it looks healthy.


### Remove obsolete upgrade code

Double check `accounting/blm/accounting.py` and
`members/blm/members.py` for any obsolete upgrade code that could be
removed.
