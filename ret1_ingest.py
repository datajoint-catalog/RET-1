#! /usr/bin/env python

import os

import re
import code
from decimal import Decimal

from datetime import datetime, timedelta

import datajoint as dj

from nwb import nwb_file
from nwb import nwb_utils

import h5py

from pymysql.err import IntegrityError

import yaml

{'unused': [code, nwb_utils]}
# 23456789_123456789_123456789_123456789_123456789_123456789_123456789_12345678


dj.config['database.host'] = 'localhost'
dj.config['database.user'] = 'chris'
dj.config['database.password'] = ''
dj.config['display.limit'] = 5
dj.config['safemode'] = False
dj.config['ingest.database'] = 'tutorial_ret1_ingest'
dj.config['production.database'] = 'catalog_ret1_dimitri'


def open_nwb(fname):
    use_nwb_file = False  # slower due to validation; more memory use
    if use_nwb_file:
        return nwb_file.open(fname, None, 'r').file_pointer
    else:
        return h5py.File(fname, 'r')


def study_from_nwb(fh):
    key = {}
    g_gen = fh['general']

    key['study'] = 'ret1'
    key['study_description'] = fh['session_description'][()].decode()
    key['institution'] = g_gen['institution'][()].decode()
    key['lab'] = g_gen['lab'][()].decode()
    key['reference_atlas'] = ''  # XXX: not in file

    Study().insert1(key)


schema = dj.schema(dj.config['ingest.database'], locals())
schema.drop(force=True)
schema = dj.schema(dj.config['ingest.database'], locals())

nwbfiledir = 'data'


@schema
class InputFile(dj.Lookup):
    definition = '''
    nwb_file: varchar(255)
    '''

    contents = [[os.path.join(nwbfiledir, f)]
                for f in os.listdir(nwbfiledir) if f.endswith('.nwb')]


# TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO
# TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO
# TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO
#
# import djcat_lab
# & copy module import dancing logic -
# for now, just reproducing here.


@schema
class Keyword(dj.Lookup):
    TODO = True
    definition = """
    # Tag of study types
    keyword	: varchar(24)
    """
    contents = zip(['behavior', 'extracellular', 'photostim'])


@schema
class Study(dj.Manual):
    definition = """
    # Study
    study		: varchar(8)	# short name of the study
    ---
    study_description	: varchar(255)	#
    institution		: varchar(255)	# institution conducting the study
    lab			: varchar(255)	# lab conducting the study
    reference_atlas	: varchar(255)	# e.g. "paxinos"
    """


@schema
class StudyKeyword(dj.Manual):
    TODO = True
    definition = """
    # Study keyword (see general/notes)
    -> Study
    -> Keyword
    """


@schema
class Publication(dj.Manual):
    TODO = True
    definition = """
    # Publication
    doi			: varchar(60)	# publication DOI
    ----
    full_citation	: varchar(4000)
    authors=''		: varchar(4000)
    title=''		: varchar(1024)
    """


@schema
class RelatedPublication(dj.Manual):
    TODO = True
    definition = """
    -> Study
    -> Publication
    """


@schema
class Subject(dj.Manual):
    definition = """
    subject_id		: int				# institution animal ID
    ---
    species		: varchar(30)
    date_of_birth	: date
    sex			: enum('M','F','Unknown')
    animal_source	: varchar(30)
    """

# END TODO END TODO END TODO END TODO END TODO END TODO END TODO END TODO
# END TODO END TODO END TODO END TODO END TODO END TODO END TODO END TODO
# END TODO END TODO END TODO END TODO END TODO END TODO END TODO END TODO


@schema
class Session(dj.Imported):

    # Note: generating animal ID here - input files only contain genotype
    definition = """
    -> Subject
    record		: int
    sample		: int
    ---
    -> Study
    session_date	: date		# session date
    session_suffix	: char(2)	# suffix for disambiguating sessions
    experimenter	: varchar(60)	# experimenter's name
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

        key['experimenter'] = g_gen['experimenter'][()].decode()

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

        if not (Subject() & key):  # ... add subject if new
            key['date_of_birth'] = '1970-01-01'  # HACK data unavail
            key['sex'] = 'Unknown'
            key['animal_source'] = 'Unknown'
            Subject().insert1(key, ignore_extra_fields=True)

        self.insert1(key, ignore_extra_fields=True)


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

    class AllEvents(dj.Part):
        definition = """
        -> Ephys.Unit
        ---
        times			: longblob	# all events
        """

    class StimulusEvents(dj.Part):

        TODO = True

        definition = """
        -> Ephys.Unit
        stim_id			: tinyint	# stimulus no
        ---
        times			: longblob	# events
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
                print('Ephys().Electrode().insert1: failed key', yaml.dump(e_key))
                raise

        #
        # Ephys.Mapping
        # XXX: SKIPPED: no cell:electrode mapping in dataset?
        #

        #
        # Ephys.Unit, Ephys.AllEvents and Ephys.StimulusEvents
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

            e_key['times'] = unit['times']

            # Ephys.AllEvents()

            try:
                Ephys().AllEvents().insert1(e_key, ignore_extra_fields=True)
            except:
                print('Ephys().AllEvents().insert1: failed key',
                      yaml.dump(u_key))
                raise

            for stim_k in [k for k in unit if 'stim_' in k]:

                e_key['stim_id'] = stim_k.split('_')[1]
                e_key['times'] = unit[stim_k]

                # Ephys.AllEvents()

                try:
                    Ephys().StimulusEvents().insert1(
                        e_key, ignore_extra_fields=True)
                except:
                    print('Ephys().StimulusEvents().insert1: failed key',
                          yaml.dump(u_key))
                    raise

        f.close()


if __name__ == '__main__':
    Session().populate()
    Ephys().populate()
    print('import complete.')
