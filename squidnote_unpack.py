#!/usr/bin/python3
"""
Program to extract individual notes from a SquidNote backup archive

   Run "squidnote_unpack -h" for usage information

N.B. The extracted files are only meant to be used as input to squidnote2xopp
and are not intended to be loaded by SquidNote, and so they have not been tested
for that use case.

Version 1.0.0 (2023-05-26)
Copyright (c) 2023, ZJ Laczik

Please submit suggestions, feature requests and bug reports on https://github.com/laczik/
"""

quiet = False

########################################
def import_libraries() :
	"""
	List all reuired libraries below either as "library_name" or as
	"(library_name, short_name)" tuple. This function will try
	to import the libraries listed and will print a summary error
	message and exit if any of the library imports fail.
	"""
	named_libs = [
		'sys',
		'io',
		'inspect',
		're',
		'struct',
		'datetime',
		'unicodedata',

		'tempfile',
		'shutil',
		'sqlite3',
		'gzip',
		'zipfile',
		'base64',
		
		('numpy', 'np'),
		'cv2',

		'argparse'
	]
	try :
		from importlib import import_module
		for named_lib in named_libs:
			if isinstance(named_lib, str) :
				lib = import_module( named_lib )
				globals()[named_lib] = lib

			elif isinstance(named_lib, tuple) :
				lib = import_module( named_lib[0] )
				globals()[named_lib[1]] = lib
	except :
		# N.B. we may not yet be able to use mprint...
		try :
			print( '\n', CRED, sys.exc_info(), CEND )
		except :
			print( '\n', CRED, '(<class \'ModuleNotFoundError\'>, ModuleNotFoundError("No module named \'sys\'") ', CEND )
		
		print( CRED, '\n\tCould not import one of the required libraries as indicated above', CEND )
		print( CRED, '\tUse pip or the package manager of your operating system to install the missing library\n', CEND )
		exit()
		
########################################

CEND	  = '\33[0m'
CWHITE  = '\33[37m'
CRED = '\33[91m'
CGREEN = '\33[92m'
CYELLOW = '\33[93m'

def mprint( *args, **kwargs) :
	"""
	print messages to stderr with optional colour specified
	wrapper for print( *args, **kwargs)
	"""
	try	:
		colour = kwargs['colour']
		del kwargs['colour']
	except KeyError :
		colour = CWHITE

	if not quiet :
		print( datetime.datetime.now(), ' ', colour, file=sys.stderr, end='' )
		print( *args, **kwargs, file=sys.stderr, end='' )
		print( CEND, file=sys.stderr )


########################################
def slugify(value, allow_unicode=False):
	"""
	Taken from https://github.com/django/django/blob/master/django/utils/text.py
	Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
	dashes to single dashes. Remove characters that aren't alphanumerics,
	underscores, or hyphens. Convert to lowercase. Also strip leading and
	trailing whitespace, dashes, and underscores.
	"""
	value = str(value)
	if allow_unicode:
		value = unicodedata.normalize('NFKC', value)
	else:
		value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
#	value = re.sub(r'[^\w\s-]', '', value.lower())
#	return re.sub(r'[-\s]+', '-', value).strip('-_')
	# replace all non word characters with '_'
	value = re.sub(r'[^-\w]', '_', value)
	# strip leading whitespace, '/' and '_'
	value = re.sub(r'^[-_/]+', '', value)
	# strip trailing whitespace, '/' and '_'
	value = re.sub(r'[-_/]+$', '', value)
	return value

########################################
def main( ) :
	"""
	This is the "main" function
	"""
	global quiet

	# programmatically import all libraries listed at the top
	import_libraries()

	# process command line arguments
	parser = argparse.ArgumentParser(
		description='Convert Squid Note files to Xournal++ format',
		epilog='Please submit buf reports on GitHub (link to be provided)'
		)

	parser.add_argument( "-f", "--filename",	action='store',			help='Backup archive file name', required=True )
	parser.add_argument( "-r", "--regex",		action='store',			help='UUID, date or file name pattern to select note' )
	parser.add_argument( "-l", "--list",		action='store_true',	help='List notes' )
	parser.add_argument( "-x", "--extract",		action='store_true',	help='Extract note' )
	parser.add_argument( "-a", "--all",			action='store_true',	help='Extract all notes' )
	parser.add_argument( "-n", "--dry-run",		action='store_true',	help='Do not write any files' )
	parser.add_argument( "-v", "--version",		action='store_true',	help='About' )
	parser.add_argument( "-q", "--quiet",		action='store_true',	help='Disable progress reporting' )

	args = parser.parse_args()

	if args.version :
		print( __doc__ )
		exit()
	quiet = args.quiet
	if not args.regex :
		regex = re.compile( '.*' )
	else :
		regex = re.compile( args.regex )
	if args.dry_run :
		mprint( f'This is a dry run, no files will be written', colour=CYELLOW )
	snb_file = args.filename
	mprint( f'Input file:  "{snb_file}"', colour=CGREEN )


	# open squidnote document archive as ZipFile object
	with zipfile.ZipFile( snb_file, 'r' ) as sn_bup :
		mprint( f'Opened squidnote backup archive "{snb_file}"' )

		with tempfile.TemporaryDirectory() as dirpath :

			# extract database to temp file (sqlite3.connect only accepts actual files)
			sn_bup.extract( 'papyrus.db', dirpath )
			db_path = dirpath + '/papyrus.db'
			# connect to database
			conn = sqlite3.connect(db_path)
			mprint( f'Connected to input sqlite3 database {db_path}', colour=CGREEN )
			# run query to get list of all notes
			cur = conn.cursor()
			cur.execute( "SELECT id, name, modified FROM note ORDER BY modified ASC" )
			query_results = cur.fetchall()
			# fix empty names and timestamp in query_results, and select notes
			note_list = []
			for i, (uuid, nn, ts) in enumerate( query_results ) :
				if not nn :
					nn = 'Untitled_' + datetime.datetime.fromtimestamp(ts/1000.0).strftime('%Y%m%d-%H%M%S')
				mtime = datetime.datetime.fromtimestamp(ts/1000.0).strftime('%Y-%m-%d %H:%M:%S')
				selected = re.match( regex, uuid ) or re.match( regex, nn ) or re.match( regex, mtime )
				if selected :
					note_list.append( (uuid, nn, mtime, ts) )
			conn.close()
			n_notes = len( note_list )
			mprint( f'Closed input database connection' )

#			print( note_list )

			if args.list :
				for i, (uuid, nn, mtime, ts) in enumerate( note_list ) :
					print( f'{i+1:04d}/{n_notes:04d}', uuid, f'"{mtime}"', f'"{nn}"' )

			elif args.extract :
				for i, (uuid, nn, mtime, ts) in enumerate( note_list ) :
					sn_file = slugify(nn) + '.squidnote'
#					sn_file = uuid+'.squidnote.zip'
					# open ZipFile archive for note being extracted				
					with zipfile.ZipFile( sn_file, 'w' ) as sn :
						mprint( f'Opened new squidnote archive for writing' )
						
						images = []
						pdfs = []
						
						# create info.json
						with sn.open( 'info.json', 'w' ) as o_file :
							o_file.write( (f'{{"id":"{uuid}","name":"{nn}","modified":{ts},"version":1}}').encode() )

						# open database for backup archive
						bup_db_conn = sqlite3.connect(db_path)
						bup_db_cursor = bup_db_conn.cursor()

						mprint( f'Connected to input sqlite3 database {db_path}' )

						with tempfile.TemporaryDirectory() as new_db_dirpath :
							# crete note.db
							new_db_path = new_db_dirpath + '/note.db'
							new_db_conn = sqlite3.connect( new_db_path )
							new_db_cursor = new_db_conn.cursor()
							sql_cmds = {
								'''CREATE TABLE android_metadata (locale TEXT)''',
								'''CREATE TABLE document(
									documentId TEXT NOT NULL,
									noteId TEXT NOT NULL,
									encryptedPassword TEXT
								)''',
								'''CREATE TABLE folder(
									id TEXT PRIMARY KEY NOT NULL,
									name TEXT NOT NULL,
									created INTEGER NOT NULL,
									trashed INTEGER,
									parentId TEXT
								)''',
								'''CREATE TABLE image( imageId TEXT NOT NULL, pageId TEXT NOT NULL, toDelete INTEGER NOT NULL )''',
								'''CREATE TABLE manifest( revision INTEGER NOT NULL )''',
								'''CREATE TABLE note(
									id TEXT PRIMARY KEY NOT NULL,
									name TEXT NOT NULL,
									created INTEGER NOT NULL,
									modified INTEGER NOT NULL,
									starred INTEGER NOT NULL DEFAULT 0,
									uiMode INTEGER NOT NULL DEFAULT 0,
									currentPageNum INTEGER NOT NULL DEFAULT 0,
									passwordHash TEXT,
									version INTEGER NOT NULL DEFAULT 0,
									trashed INTEGER,
									parentId TEXT,
									revision INTEGER NOT NULL DEFAULT 0
								)''',
								'''CREATE TABLE page(
									id TEXT PRIMARY KEY NOT NULL,
									noteId TEXT NOT NULL,
									created INTEGER NOT NULL,
									modified INTEGER NOT NULL,
									pageNum INTEGER NOT NULL,
									offsetX REAL NOT NULL DEFAULT 0,
									offsetY REAL NOT NULL DEFAULT 0,
									zoom REAL NOT NULL DEFAULT 1,
									fitMode INTEGER NOT NULL DEFAULT 0,
									documentId TEXT
								)'''
							}
							for sql_cmd in sql_cmds :
								new_db_cursor.execute( sql_cmd )

							# add data
							#   N.B. for one value item comma is required to create tuple (as opposed to grouped expression of single string)

							# TABLE android_metadata
							sql_vals = tuple( ['en_GB'] )
							new_db_cursor.execute("INSERT INTO android_metadata VALUES (?)", sql_vals )
							new_db_conn.commit()

							# TABLE note
							new_db_cursor.execute("INSERT INTO note (id,name,created,modified) VALUES (?,?,?,?)", (uuid,nn,ts,ts) )
							new_db_conn.commit()
							
							# TABLE document (PDF backgrounds)
							documentId = ''
							bup_db_cursor.execute( f'SELECT documentId, noteId FROM document WHERE noteId IS "{uuid}"' )
							pdf_sql_vals = bup_db_cursor.fetchall()
							if pdf_sql_vals :
								new_db_cursor.executemany("INSERT INTO document(documentId,noteId) VALUES (?,?)", pdf_sql_vals )
								new_db_conn.commit()
								# copy pdf file(s) to Zip archive
								for documentId, noteId in pdf_sql_vals :
									pdfs.append( documentId )

							# TABLE page
							bup_db_cursor.execute( f'SELECT id, noteId, created, modified, pageNum FROM page WHERE noteId IS "{uuid}"' )
							page_sql_vals = bup_db_cursor.fetchall()
							page_sql_vals_ext = [ (*page_sql_val, documentId) for page_sql_val in page_sql_vals ]
							if page_sql_vals_ext :
								new_db_cursor.executemany("INSERT INTO page(id,noteId,created,modified,pageNum,documentId) VALUES (?,?,?,?,?,?)",
															page_sql_vals_ext )
								new_db_conn.commit()

							# TABLE image one entry for every image in every page
							# loop over pages
							for (page_uuid,note_uuid,created,modified,page_num) in page_sql_vals :
								bup_db_cursor.execute( f'SELECT imageId, pageId, toDelete FROM image WHERE pageId IS "{page_uuid}"' )
								img_sql_vals = bup_db_cursor.fetchall()
								if img_sql_vals :
									new_db_cursor.executemany("INSERT INTO image(imageId,pageId,toDelete) VALUES (?,?,?)", img_sql_vals )
									new_db_conn.commit()
									# copy image file)s) to Zip archive
									for imageId, pageId, toDelete in img_sql_vals :
										images.append( imageId )

							new_db_conn.close()
							bup_db_conn.close()
							# copy new database to note Zip archive
							with sn.open( 'note.db', 'w' ) as o_file :
								with open(new_db_path, 'rb') as i_file:
									shutil.copyfileobj( i_file, o_file)
									i_file.close()
								o_file.close()

#							# copy new database to current directory
#							with open( 'note.db', 'wb' ) as o_file :
#								with open(new_db_path, 'rb') as i_file:
#									shutil.copyfileobj( i_file, o_file)
#									i_file.close()
#								o_file.close()

						# add .metadata an note.page to data/pages/
						with sn.open( 'data/pages/.metadata', 'w' ) as o_file :
							o_file.write( ('').encode() )
						page_set = list( set( [ page_uuid for (page_uuid,note_uuid,created,modified,page_num) in page_sql_vals ] ) )
						l = len( page_set )
						for page in page_set :
							with sn.open( f'data/pages/{page}.page', 'w' ) as o_file :
								with sn_bup.open( f'data/pages/{page}.page', 'r' ) as i_file:
									shutil.copyfileobj( i_file, o_file)
									i_file.close()
								o_file.close()
						mprint( f'Written {l} file(s) to "data/pages"' )
						
						# add .metadata and images to data/imgs/
						with sn.open( 'data/imgs/.metadata', 'w' ) as o_file :
							o_file.write( ('').encode() )
						# copy images
#						print( 'images: ', list( set( images ) ) )
						image_set = list( set( images ) )
						l = len( image_set )
						for image in image_set :
							with sn.open( f'data/imgs/{image}', 'w' ) as o_file :
								with sn_bup.open( f'data/imgs/{image}', 'r' ) as i_file:
									shutil.copyfileobj( i_file, o_file)
									i_file.close()
								o_file.close()
						mprint( f'Written {l} file(s) to "data/imgs"' )
						
						# add .metadata and background PDFs to data/docs/
						with sn.open( 'data/docs/.metadata', 'w' ) as o_file :
							o_file.write( ('').encode() )
						# copy background PDFs
#						print( 'pdfs:   ', list( set( pdfs ) ) )
						pdf_set = list( set( pdfs ) )
						l = len( pdf_set )
						for pdf in pdf_set :
							with sn.open( f'data/docs/{pdf}', 'w' ) as o_file :
								with sn_bup.open( f'data/docs/{pdf}', 'r' ) as i_file:
									shutil.copyfileobj( i_file, o_file)
									i_file.close()
								o_file.close()
						mprint( f'Written {l} file(s) to "data/docs"' )



						sn.close()
						mprint( f'{i+1:04d}/{n_notes:04d}', f'Extracted squidnote "{sn_file}"', colour=CGREEN )

#	if not args.dry_run :
#		pass



	# we are done
	mprint( f'Finished', colour=CGREEN )

########################################
if __name__ == "__main__":
	main()

