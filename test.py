import datajoint as dj
dj.config['database.host'] = 'tutorial-db.datajoint.io'
dj.config['database.user'] = 'dimitri'
dj.config['names.djcat_lab'] = 'catalog_lab_dimitri'

schema = dj.schema('dimitri_test', locals())

@schema
class A(dj.Manual):
    definition = """
    a  : int 
    """
    
@schema
class B(dj.Manual):
    definition = """ 
    -> A
    """

@schema 
class C(dj.Manual):
    definition = """
    -> B
    (c) -> A
    ---
    """

