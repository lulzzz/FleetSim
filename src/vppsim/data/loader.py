#!/usr/bin/env python

import os
import pandas as pd
from pathlib import Path

import logging
logger = logging.getLogger(__name__)

from vppsim import data


PROJECT_DIR = str(Path(__file__).resolve().parents[3])
CAR2GO_PATH = PROJECT_DIR + '/data/raw/car2go/'
PROCESSED_DATA_PATH = PROJECT_DIR + '/data/processed/'
PROCESSED_DATA_FILE = PROCESSED_DATA_PATH + '/trips.pkl'
CAR2GO_FILES = ['stuttgart.2016.03.22-2016.11.30.csv', 'stuttgart.2016.12.01-2017.02.22.csv', 'stuttgart.2017.02.23-2017-05-01.csv', 'stuttgart.2017.05.01-2017.10.31.csv', 'stuttgart.2017.11.01-2018.01.31.csv']


def main():
    print(load_car2go(rebuild=True))


def load_car2go(rebuild=False):
    '''Loads processed data into a dataframe, process again if needed'''


    if not os.path.exists(PROCESSED_DATA_PATH):
        os.makedirs(PROCESSED_DATA_PATH)

    for f in CAR2GO_FILES:
        path = PROCESSED_DATA_PATH + 'trips.' + f.strip('stuttgart.').strip('.csv') + '.pkl'
        if rebuild is True or os.path.isfile(path) is False:
            logger.info('Processing %s...' % f)
            df = pd.read_csv(CAR2GO_PATH + f)
            df = data.process_car2go(df)
            df.to_csv(path + '.csv')
            pd.to_pickle(df, path)
            logger.info('Saved processed %s to disk.' % f)
        else:
            logger.info('Processed %s already found on disk' %f)

    if rebuild is True or os.path.isfile(PROCESSED_DATA_FILE) is False:
        pkls = []
        logger.info('Concatening all files together...')
        for f in CAR2GO_FILES:
            path = PROCESSED_DATA_PATH + 'trips.' + f.strip('stuttgart.').strip('.csv') + '.pkl'
            pkls.append(pd.read_pickle(path))

        df = pd.concat(pkls).sort_values(['start_time']).reset_index()
        df.to_csv(PROCESSED_DATA_FILE.strip('.pkl') + '.csv')
        pd.to_pickle(df, PROCESSED_DATA_FILE)
        logger.info('Wrote all processed files to %s' % PROCESSED_DATA_FILE)

    return pd.read_pickle(PROCESSED_DATA_FILE)


if __name__ == '__main__':
    main()
