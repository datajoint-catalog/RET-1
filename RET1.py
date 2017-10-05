import datajoint as dj

dj.config['database.host'] = 'localhost'
dj.config['database.user'] = 'chris'
dj.config['ingest.database'] = 'tutorial_ret1_ingest'

schema = dj.schema(dj.config['production.database'], locals())

# TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO
# TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO
# TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO
#
# import djcat_lab
# & copy module import dancing logic -
# for now, just reproducing here.


@schema
class Keyword(dj.Lookup):
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
    lab			: varchar(255)	#  lab conducting the study
    reference_atlas	: varchar(255)	# e.g. "paxinos"
    """


@schema
class StudyKeyword(dj.Manual):
    definition = """
    # Study keyword (see general/notes)
    -> Study
    -> Keyword
    """


@schema
class Publication(dj.Manual):
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
class Session(dj.Manual):
    # XXX: generating animal ID here - input files only contain genotype
    definition = """
    -> Subject
    session		: int		# session within
    ---
    -> Study
    session_date	: date		# session date
    session_suffix	: char(2)	# suffix for disambiguating sessions
    experimenter	: varchar(60)	# experimenter's name
    session_start_time	: datetime
    """


@schema
class Ephys(dj.Manual):
    definition = """
    -> Session
    """

    class Electrode(dj.Part):
        definition = """
        -> Ephys
        electrode	: tinyint	# electrode no
        ---
        electrode_x	: decimal(3,2)	# (x in mm)
        electrode_y	: decimal(3,2)	# (y in mm)
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

    class Events(dj.Part):
        definition = """
        -> Ephys.Unit
        ---
        stim_1		: longblob	# stim_1 events
        stim_2		: longblob	# stim_2 events
        stim_3		: longblob	# stim_3 events
        all		: longblob	# all events
        """


@schema
class Stimulus(dj.Manual):
    definition = """
    -> Session
    """

    class Trial(dj.Part):
        definition = """
        -> Stimulus
        trial		: smallint	# trial within a session
        ---
        start_time	: float
        stop_time	: float
        """

    class StimulusPresentation(dj.Part):

        # XXX: len(timestamps) varies w/r/t len(data); timestamps definitive
        # ... actually 'num_samples' definitive, but same as len(timestamps)
        #     and so is redundant and discarded.

        definition = """
        -> Stimulus.Trial
        ---
        bpp		: tinyint	# bits per pixel
        size		: decimal(3,2)	# size (mm)
        x		: tinyint
        y		: tinyint
        dx		: tinyint
        dy		: tinyint
        timestamps	: longblob
        data		: longblob
        """


@schema
class RF(dj.Manual):
    # TODO implement
    definition = """
    -> Session
    """
