"""
exo2geo.py
Rupert Deese
October 2013

Script to translate Exodus II files (so far only produced in CUBIT) into geoFEST format.

Usage: python exo2geo.py inputFile.exo

Input:

An Exodus II file (produced in CUBIT is all that I have tested). The model in the 
Exodus II file is expected to contain 3 nodesets and at minimum 1 sideset. The nodesets
correspond to boundary conditions: nodes in nodeset 1 are fixed in x, nodes in nodeset 2
are fixed in y, and nodes in nodeset 3 are fixed in z. The required sideset defines the
surface at which the surface traction is applied. All subsequent sidesets are boundary
surfaces at which a buoyancy condition is applied. Element type for geoFEST is determined
by the block number assigned to the element in the exodus file. Hence, any sideset
defining a buoyancy condition should separate two different blocks.

The script asks for input at runtime to fill in the surface traction force and
direction, and buoyancy densities and vectors.

Output: 
Incomplete versions of the main files required for a geoFEST run:

coord.dat
bcc.dat
eldata.dat
surfdata.dat
buoydata.dat

TODO:

- Improve program robustness: currently program does basic checking for malformed input.
- Test with no sidesets: should behave correctly now or with minimal debugging. 
	Ideal result would be empty buoydata.dat and surfdata.dat files.
- Finish commenting code.

"""

import sys
import os
import subprocess

##################################################################
## Helper functions for read/write

def readInputToList(inputFile, outputList):
	endLine = outputList[-1] if len(outputList) != 0 else ''
	line = inputFile.readline()
	while endLine != ';':
		outputList += map(lambda X: X[:-1] if X[-1] == ',' else X, line.split())
		line = inputFile.readline()
		endLine = outputList[-1]
	del outputList[-1]
def getGFESTSide(side):
	if side == 1:
		return 3
	elif side == 2:
		return 1
	elif side == 3:
		return 2
	elif side == 4:
		return 4
	else:
		sys.stderr.write("Exodus file parsing error: side # " + side + " of element " + \
			els(i) + " out of range!")
		return None

def writeCoords(numNodes):
	print 'Writing node coordinate data...'
	crdFile = open('coord.dat', 'w')
	for i in range(numNodes):
		crdFile.write(str(i+1) + ' ' + str(1000*float(coords[i])) + ' ' + str(1000*float(coords[i+numNodes])) 
			+ ' ' + str(1000*float(coords[i+2*numNodes])) + '\n')
	crdFile.write('0 0\n')
	crdFile.close()

def writeBCC(bcc):
	print 'Writing boundary condition data...'
	bccFile = open('bcc.dat', 'w')
	for line in bcc:
		bccFile.write(' '.join(map(str, line)) + '\n')
	bccFile.write("0 0\n")
	bccFile.close()

def writeElems(elems):
	print 'Writing element connectivity data...'
	elemFile = open('eldata.dat', 'w')
	for line in elems:
		elemFile.write(' '.join(map(str, line)) + '\n')
	elemFile.write("0 0\n")
	elemFile.close()

def writeSurfData(elsSides):
	print 'Writing surface traction data...'
	sideList = open('surfdata.dat', 'w')
	forceVector = raw_input("Enter a floating point {X,Y,Z} as \"X Y Z\" vector for surface traction: ")
	if len(forceVector.split()) != 3:
		sys.stderr.write("User input error: wrong dimension of vector entered.")
	for line in elsSides:
		sideList.write(' '.join(map(str, line)) + ' ' + forceVector + "\n")
	sideList.write("0 0\n")
	sideList.close()

def writeBuoyData(buoyData):
	print 'Writing bouyancy data (in order of increasing sideset #)...'
	buoyFile = open('buoydata.dat', 'w')
	for sideSet in buoyData:
		forceVector = raw_input("Enter a floating point {X,Y,Z} as \"X Y Z\" vector for buoyancy direction: ")
		if len(forceVector.split()) != 3:
			sys.stderr.write("User input error: wrong dimension of vector entered.")
		buoyancy = raw_input("Enter a buoyancy value (rho*g): ")
		buoyFile.write(str(len(sideSet)) + ' ' + forceVector + ' ' + buoyancy + '\n')
		for line in sideSet:
			buoyFile.write(' '.join(map(str, line)) + "\n")
		buoyFile.write('0 0\n')
	buoyFile.close()

##################################################################

## ACTUAL PROGRAM EXECUTION STARTS HERE

##################################################################
## File handling

# Get path, cd into directory of exo file.
if not os.path.exists(sys.argv[1]):
	raise OSError('Invalid directory and/or file provided.\nUsage: python exo2geo.py inputFile.exo')

path = sys.argv[1].split('/')
filename, ext = path[-1].split('.')

if ext != 'exo':
	raise IOError('Non-Exodus filetype provided as input (or wrong extension used).' + \
				  '\nUsage: python exo2geo.py inputFile.exo')

# If the CWD is not the same as the exo file's, change it to the folder containing the exo file.
if len(path) > 1:
	try:
		os.chdir(os.getcwd()+'/'+reduce(lambda X,Y: X+'/'+Y,path[:-1]))
	except OSError:
		raise IOError('Invalid directory provided.')

# Convert to txt file using ncdump utility (part of netCDF)
exoFile = open(filename+'.txt', 'w')

try:
	subprocess.Popen(['ncdump', path[-1]], stdout=exoFile).wait()
except OSError:
	raise OSError('\'ncdump\' command not found. exo2geo requires netCDF to run.')

exoFile.close()

exoFile = open(filename+'.txt', 'r')


##################################################################
## Parsing text dump of exo file.

###############
# Case switching:
# 0 = nothing
# 1 = coordinate input
# 2 = nodeset input (BCs)
# 4 = Element connectivity
# 5 & 6 = Side set 1 (surface traction)
# 7 & 8 = Side sets 2 and up (buoyancy boundaries)
###############

# Starting values for key program data.
buoyData = []
elems = []
elemNum = 1
case = 0

# Start reading the file.
line = exoFile.readline()
while len(line) != 0:
	data = line.split()

	# For every line that isn't just a newline:
	if len(data) != 0:
		# CASE 0: Parse headers to redirect to other cases.
		if case == 0:
			if data[0] == 'num_nodes':
				numNodes = int(data[2])
				bcc = map(lambda X: [X+1, 0], range(numNodes))
			elif data[0] == 'coord':
				case = 1
			elif data[0][:-1] == 'node_ns':
				case = 2
			elif data[0][:-1] == 'connect':
				elemType = data[0][-1]
				#print 'elemType = ', elemType
				case = 4
			elif data[0] == 'elem_ss1':
				case = 5
			elif data[0] == 'side_ss1':
				case = 6
			elif data[0][:-1] == 'elem_ss':
				sideSetNum = data[0][-1]
				case = 7
			elif data[0][:-1] == 'side_ss':
				case = 8

		# GET NODE COORDINATES
		if case == 1:
			print 'Getting node coordinates...'
			coords = []
			readInputToList(exoFile, coords)
			writeCoords(numNodes)
			case = 0

		# GET BOUNDARY CONDITIONS
		if case == 2:
			print 'Getting boundary conditions...'
			nodes = map(lambda X: X[:-1] if X[-1] == ',' else X, data[2:])
			readInputToList(exoFile, nodes)
			if int(data[0][-1]) > 3:
				print 'Getting nodes to plot data for...'
				plotNodes = nodes
			else:
				for i in range(numNodes):
					bcc[i].append(0) if str(i+1) in nodes else bcc[i].append(1)
			## By convention, nodes_ns1 is fixed in x, node_ns2 is fixed in y, and node_ns3 is fixed in z
			case = 0

		# GET ELEMENTS
		if case == 4:
			print 'Getting element connectivity...'
			endline = ''
			line = exoFile.readline()
			while endline != ';':
				elems.append([elemNum, 0, elemType] + map(lambda X: X[:-1] if X[-1] == ',' else X, line.split()))
				endline = elems[-1][-1]
				elemNum += 1
				line = exoFile.readline()
			del(elems[-1][-1])
			case = 0

		# GET SURFACE TRACTION DATA
		if case == 5:
			print 'Getting surface traction data...'
			els = map(lambda X: X[:-1] if X[-1] == ',' else X, data[2:])
			readInputToList(exoFile, els)
			case = 0
		# GET SURFACE TRACTION DATA
		if case == 6:
			print 'Getting surface traction data...'
			sides = map(lambda X: X[:-1] if X[-1] == ',' else X, data[2:])
			readInputToList(exoFile, sides)

			elsSides = []
			for i in range(len(els)):
				elsSides.append([int(els[i])])
				elsSides[i].append(getGFESTSide(int(sides[i])))
			writeSurfData(elsSides)
			case = 0

		# GET BUOYANCY DATA
		if case == 7:
			print 'Getting buoyancy data...'
			els = map(lambda X: X[:-1] if X[-1] == ',' else X, data[2:])
			readInputToList(exoFile, els)
			case = 0
		# GET BUOYANCY DATA
		if case == 8:
			print 'Getting buoyancy data...'
			sides = map(lambda X: X[:-1] if X[-1] == ',' else X, data[2:])
			readInputToList(exoFile, sides)

			elsSides = []
			for i in range(len(els)):
				elsSides.append([int(els[i])])
				elsSides[i].append(getGFESTSide(int(sides[i])))
			buoyData.append(elsSides)
			case = 0

	# Read next line
	line = exoFile.readline()

# Create dummy stress file.
out = open('stresses.dat','w')
for i in range(elemNum):
	out.write(' '.join(['0']*10) + '\n')
out.close()

# Create file giving nodes to plot
out = open('plotNodes.dat', 'w')
out.write(' '.join(plotNodes)+'\n')
out.close

# have to do this at the end since BCC and element data requires reads from multiple node lists.
writeElems(elems)
writeBCC(bcc)
writeBuoyData(buoyData)
exoFile.close()




