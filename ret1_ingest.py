#! /usr/bin/env python

import os

import re
from datetime import datetime
from decimal import Decimal
from importlib import reload

import datajoint as dj

from nwb import nwb_file

import h5py

from pymysql.err import IntegrityError

import yaml

config = 'local'
# config = 'cloud'

dj.config['display.limit'] = 5
dj.config['safemode'] = False

if config == 'local':
    dj.config['database.host'] = 'localhost'
    dj.config['database.user'] = 'chris'
    dj.config['database.password'] = ''
    dj.config['ingest.database'] = 'tutorial_ret1_ingest'
    dj.config['names.djcat_lab'] = 'tutorial_ret1_lab_ingest'

if config == 'cloud':
    dj.config['database.host'] = 'tutorial-db.datajoint.io'
    dj.config['database.user'] = 'chris'
    # dj.config['database.password'] = ''
    dj.config['ingest.database'] = 'catalog_ret1_ingest_new'
    dj.config['names.djcat_lab'] = 'catalog_ret1_lab_ingest_new'


import djcat_lab as lab
schema = dj.schema(dj.config['ingest.database'], locals())

nwbfiledir = 'data'


def open_nwb(fname):
    '''
    open_nwb: wrapper to open nwb files
    '''
    use_nwb_file = False  # slower due to validation; more memory use
    if use_nwb_file:
        return nwb_file.open(fname, None, 'r').file_pointer
    else:
        return h5py.File(fname, 'r')


def study_from_nwb(fh):
    '''
    simple procedural function to load the djcat_lab information
    '''
    key = {}
    g_gen = fh['general']

    key['study'] = 'ret1'
    key['study_description'] = fh['session_description'][()].decode()
    key['institution'] = g_gen['institution'][()].decode()
    key['lab'] = g_gen['lab'][()].decode()
    key['reference_atlas'] = ''  # XXX: not in file

    lab.Lab().insert1(key, ignore_extra_fields=True)
    lab.Study().insert1(key, ignore_extra_fields=True)


@schema
class InputFile(dj.Lookup):
    definition = '''
    nwb_file: varchar(255)
    '''

    contents = [[os.path.join(nwbfiledir, f)]
                for f in os.listdir(nwbfiledir) if f.endswith('.nwb')]


@schema
class Session(dj.Imported):
    definition = """
    -> lab.Subject
    session  :  int 
    ---
    -> lab.Study
    record         : int
    sample         : int
    session_date	: date		# session date
    session_suffix	: char(2)	# suffix for disambiguating sessions
    (experimenter) -> lab.User
    session_start_time	: datetime
    -> InputFile
    """
    sess_re = re.compile('.*?\[(.*?)\].*\[(.*?)\]')  # RecNo: [4]; SmplNo: [2]

    @property
    def key_source(self):
        return InputFile()

    def _make_tuples(self, key):

        #
        # Open File / Process filename
        #

        fname = key['nwb_file']  # YYYYMMDD_RN.nwb
        print('Session()._make_tuples: nwb_file', key['nwb_file'])

        f = open_nwb(key['nwb_file'])

        (fdate, sfx) = os.path.split(fname)[-1:][0].split('_')
        sfx = sfx.split('.')[0]

        key['session_date'] = fdate  # XXX: from session_start_time instead?
        key['session_suffix'] = sfx

        #
        # General Study Information (in all files - only load 1x)
        #

        key['study'] = 'ret1'
        try:
            study_from_nwb(f)
        except IntegrityError as e:
            if 'Duplicate entry' in e.args[1]:
                pass
            else:
                raise

        #
        # General Session Information
        #

        g_gen = f['general']

        s_string = g_gen['session_id'][()].decode()
        (record, sample) = Session.sess_re.match(s_string).groups()

        key['record'] = record
        key['sample'] = sample
        key['session'] = int(record + sample)

        key['full_name'] = g_gen['experimenter'][()].decode()
        key['username'] = key['full_name'].split(' ')[0]
        key['experimenter'] = key['username']

        if not (lab.User() & key):
            lab.User().insert1(key, ignore_extra_fields=True)

        stime = f['session_start_time'][()].decode()
        stime = datetime.strptime(stime, '%a %b %d %Y %H:%M:%S')
        key['session_start_time'] = stime

        # Subject
        #
        # Note:
        #
        # Input files did not contain subject identifiers -
        # assuming 1:1 genotype:subject for illustration.
        # *Not* using dj.Lookup for this since it is faked data.

        genotypes = [
            'KO (chx10)',
            'KO (pax6)',
            'KO bax -/- (chx10)',
            'WT (chx10 het)',
            'WT (pax6 het)',
        ]

        sids = {key: value for (key, value)
                in zip(genotypes, range(len(genotypes)))}

        g_subject = g_gen['subject']

        genotype = g_subject['genotype'][()].decode()
        key['genotype'] = genotype

        key['subject_id'] = sids[genotype]
        key['species'] = g_subject['species'][()].decode()

        if not (lab.Subject() & key):  # ... add subject if new
            key['date_of_birth'] = '1970-01-01'  # HACK data unavail
            key['sex'] = 'Unknown'
            key['animal_source'] = 'Unknown'
            lab.Subject().insert1(key, ignore_extra_fields=True)

        self.insert1(key, ignore_extra_fields=True)

        f.close()


@schema
class Ephys(dj.Computed):

    definition = """
    -> Session
    """

    class Electrode(dj.Part):
        definition = """
        -> Ephys
        electrode	: tinyint	# electrode no
        ---
        electrode_x	: decimal(5,2)	# (x in mm)
        electrode_y	: decimal(5,2)	# (y in mm)
        """

    # XXX: do we actually have a cell mapping in dataset?
    class Mapping(dj.Part):
        definition = """
        -> Ephys
        """

    class Unit(dj.Part):
        definition = """
        -> Ephys
        cell_no		: int		# cell no
        """

    class Spikes(dj.Part):
        definition = """
        -> Ephys.Unit
        ---
        spike_times	: longblob	# all events
        """

    def _make_tuples(self, key):
        ''' Ephys._make_tuples '''

        key['nwb_file'] = (Session() & key).fetch1()['nwb_file']
        print('Ephys()._make_tuples: nwb_file', key['nwb_file'])

        f = h5py.File(key['nwb_file'], 'r')

        #
        # Ephys
        #

        self.insert1(key, ignore_extra_fields=True)

        g_gen = f['general']
        g_ephys = g_gen['extracellular_ephys']
        g_proc = f['processing']

        #
        # Ephys.Electrode
        #

        e_key = dict(key)  # clean copy
        for i in range(len(g_ephys['electrode_map'])):

            (x, y, __,) = g_ephys['electrode_map'][i]

            e_key['electrode'] = i  # XXX: synthetic
            e_key['electrode_x'] = Decimal(float(x))
            e_key['electrode_y'] = Decimal(float(y))

            try:
                Ephys.Electrode().insert1(e_key, ignore_extra_fields=True)
            except:
                print('Ephys().Electrode().insert1: failed key')
                print(yaml.dump(e_key))
                raise

        #
        # Ephys.Mapping
        # XXX: SKIPPED: no cell:electrode mapping in dataset?
        #

        #
        # Ephys.Unit & Ephys.Spikes
        #

        g_units = g_proc['Cells']['UnitTimes']

        u_key = dict(key)  # for units
        e_key = dict(key)  # for events

        for unit_k in [k for k in g_units if 'cell_' in k]:

            unit = g_units[unit_k]
            unit_id = unit_k.split('_')[1]

            u_key['cell_no'] = e_key['cell_no'] = unit_id

            # Ephys.Unit()

            try:
                Ephys.Unit().insert1(u_key, ignore_extra_fields=True)
            except:
                print('Ephys().Unit().insert1: failed key', yaml.dump(u_key))
                raise

            # Ephys.Spikes()
            # Note: individual spike data e.g. unit['stim_1'] discarded;
            # they are already concatenated together to form spike_times 

            e_key['spike_times'] = unit['times'].value

            try:
                Ephys().Spikes().insert1(e_key, ignore_extra_fields=True)
            except:
                print('Ephys().AllEvents().insert1: failed key',
                      yaml.dump(u_key))
                raise

        f.close()


@schema
class Movie(dj.Computed):
    definition = """
    movie_id		: smallint	# movie IDs
    ----
    x			: int
    y			: int
    dx			: int
    dy			: int
    dim_a		: int
    dim_b		: int
    bpp			: tinyint	# bits per pixel
    pixel_size		: decimal(3,2)	# (mm)
    movie		: longblob	# 3d array
    source_fname	: varchar(255)	# source file
    -> InputFile
    """

    @property
    def key_source(self):
        return InputFile()
    
    def _make_tuples(self, key):
        ''' Movie._make_tuples '''

        key['nwb_file'] = (Session() & key).fetch1()['nwb_file']
        print('Movie()._make_tuples: nwb_file', key['nwb_file'])

        f = h5py.File(key['nwb_file'], 'r')

        # /stimulus/presentation/rec_stim_N/timeseries : group
        # /stimulus/presentation/rec_stim_N/timeseries/data : movie

        g_pres = f.get('/stimulus/presentation')

        for stim in (g_pres[k] for k in g_pres if 'rec_stim_' in k):

            movie = stim['data']
            source_fname = movie.file.filename.split('/')[-1:][0]

            if(self & dict(source_fname=source_fname)):
                continue

            print('loading movie', source_fname, 'from', stim.name)

            # generate synthetic 'autoincrement' movie_id
            movie_id = (dj.U().aggr(Movie(),
                n='max(movie_id)').fetch1('n') or 0)+1

            self.insert1({
                'movie_id': movie_id,
                'x': int(stim['meister_x'][()]),
                'y': int(stim['meister_y'][()]),
                'dx': int(stim['meister_dx'][()]),
                'dy': int(stim['meister_dy'][()]),
                'dim_a': int(stim['dimension'][0]),
                'dim_b': int(stim['dimension'][1]),
                'bpp': int(stim['bits_per_pixel'][()]),
                'pixel_size': Decimal(float(stim['pixel_size'][()])),
                'movie': movie.value,
                'source_fname':	source_fname,
                'nwb_file': key['nwb_file']
            })

        f.close()


@schema
class Stimulus(dj.Computed):

    definition = """
    -> Session
    """

    class Trial(dj.Part):

        # XXX: len(timestamps) varies w/r/t len(movie); timestamps definitive
        # ... actually 'num_samples' definitive, but same as len(timestamps)
        #     and so is redundant and discarded.

        definition = """
        -> Stimulus
        trial_idx	: smallint	# trial within a session
        ---
        -> Movie
        start_time	: float		# (s)
        stop_time	: float		# (s)
        timestamps	: longblob	# (s)
        """

    def _make_tuples(self, key):
        ''' Stimulus._make_tuples '''

        nwb_file = (Session() & key).fetch1()['nwb_file']
        print('Stimulus()._make_tuples: nwb_file', nwb_file)

        f = h5py.File(nwb_file, 'r')

        #
        # Stimulus
        #
        # /epochs/stim_N : group

        self.insert1(key, ignore_extra_fields=True)

        g_epochs = f['epochs']

        #
        # Stimulus.Trial
        #
        # /epochs/stim_N : group
        # /epochs/stim_N/timeseries : group

        for stim_k in [k for k in g_epochs if 'stim_' in k]:

            stim = g_epochs[stim_k]
            stim_ts = stim['stimulus']['timeseries']
            stim_id = stim_k.split('_')[1]

            key['trial_idx'] = stim_id
            key['start_time'] = stim['start_time'][()]
            key['stop_time'] = stim['stop_time'][()]
            key['timestamps'] = stim_ts['timestamps'].value
            
            movie_fname = stim_ts['data'].file.filename.split('/')[-1:][0]

            key['movie_id'] = (Movie() &
                dict(source_fname=movie_fname)).fetch1('movie_id')

            try:
                Stimulus.Trial().insert1(key, ignore_extra_fields=True)
            except:
                print('Stimulus().insert1: failed key', yaml.dump(key))
                raise

        f.close()


if __name__ == '__main__':
    Session().populate()
    Ephys().populate()
    Movie().populate()
    Stimulus().populate()
    print('import complete.')
