import datajoint as dj
import djcat_lab as lab

schema = dj.schema(dj.config['names.djcat_ret1'], locals())


@schema
class Session(dj.Manual):
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
    """


@schema
class Ephys(dj.Imported):
    definition = """
    -> Session
    """

    class Electrode(dj.Part):
        definition = """
        -> Ephys
        electrode	: smallint	# electrode no
        ---
        electrode_x	: decimal(3,2)	# (x in mm)
        electrode_y	: decimal(3,2)	# (y in mm)
        """

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


@schema
class Movie(dj.Manual):
    definition = """
    movie_id   :  smallint   # movie IDs
    ----
    x		   : int
    y		   : int
    dx		   : int
    dy		   : int
    dim_a	   : int
    dim_b		: int
    bpp		: tinyint	# bits per pixel
    pixel_size	: decimal(3,2)	# (mm)
    """


@schema
class Stimulus(dj.Imported):
    definition = """
    # A stimulus session comprising multiple trials
    -> Session
    """

    class Trial(dj.Part):

        definition = """
        -> Stimulus
        trial_idx  :  smallint  # trial within 
        ---
        -> Movie
        start_time	: float    # (s)
        stop_time	: float    # (s)
        timestamps	: longblob # (s)
        """


@schema
class RF(dj.Computed):
    definition = """
    # Receptive Fields
    -> Ephys
    -> Stimulus 
    """
     
    class Unit(dj.Part):
        definition = """
        # Receptive fields
        -> RF
        -> Ephys.Spikes
        ----
        rf : longblob 
        """
