from nvme_mon.app import main

import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

log = logging.getLogger(__name__)

if __name__ == "__main__":
    log.debug('calling app.main')
    main()
