#!/usr/bin/env python3
import os
import sys
from hashlib import sha1
from functools import partial
from PIL import Image

def sha1sum(filename: str):
	with open(filename, 'rb') as reading:
		return sha1(reading.read()).digest()

def image_hash(filename, bytes_per_row=1, height=8, bits_per_color=0):
	width = bytes_per_row*8 + 1
	try:
		image = Image.open(filename)
	except OSError:
		print(f"Ignoring non-image {filename}", file=sys.stderr)
		return None

	shape = image.resize((width, height)).convert('L').tobytes()
	histogram = image.histogram()

	digest = ""
	for column in range(0, width*height, width):
		total = 0
		for i in range(width-1):
			total <<= 1
			total += (shape[column+i] > shape[column+i+1])
		digest += (f"%0{bytes_per_row*2}x") % total

	if not bits_per_color:
		return digest

	ret = 0
	step = 256 // (bits_per_color + 1)
	for offset in range(0, len(histogram), len(histogram)//3):
		ret <<= 1
		start = 256 - step//2 + offset
		total = sum(histogram[start:offset+256])
		while start > offset:
			next_total = sum(histogram[start:start+step])
			ret += total > next_total
			ret <<= 1
			total = next_total
			start -= step
		ret += total > sum(histogram[offset:start+step])
	digest += f"%0{(bits_per_color*3)//8}x" % ret
	return digest

def update_hashdict(filename, hash_func, locations, tolerance=0):
	#don't bother looking up all hashes
	digest = hash_func(filename)
	if digest is None:
		return

	if not tolerance:
		if locations.get(digest) is None:
			locations[digest] = [filename]
		else:
			locations[digest].append(filename)
		return

	for hash_ in locations:
		if hamming(hash_, digest) < tolerance:
			locations[hash_].append(filename)
			return
	locations[digest] = [filename]

def findclash(dirs, tolerance=-1, colors=False):
	locations = {}
	func = sha1sum
	if tolerance > 0:
		if colors:
			func = partial(image_hash, height=5, bits_per_color=8)
		else:
			func = image_hash
	else:
		tolerance = 0

	for directory in dirs:
		directory = os.path.expanduser(directory)
		if os.path.isfile(directory):
			update_hashdict(directory, func, locations, tolerance)
			#func(directory, locations)
			continue
		files = os.listdir(directory)
		for file in files:
			file = os.path.join(directory, file)
			if os.path.isfile(file):
				update_hashdict(file, func, locations, tolerance)

	return locations

def hamming(x: str, y: str):
	'''Hamming distance between two hex strings'''
	diff = int(x, 16) ^ int(y, 16)
	ret = 0
	while diff > 0:
		ret += diff & 1
		diff >>= 1
	return ret

def main():
	import argparse

	parser = argparse.ArgumentParser(description="Compare hashes within a directory")
	parser.add_argument("-i", help="Use image hash (with fuzziness value from 0-64)"
		, dest="fuzz", type=int, nargs='?', const=5, default=-1)
	parser.add_argument("-c", help="Use colored variant of image hash"
		, dest="colored", action="store_true")
	parser.add_argument("-a", help="(Piping stdout) include all clashed " \
		"files instead of all but one", dest="all_clash", default=1, const=0
		, action="store_const")
	parser.add_argument("-d", help="(Current directory only) Move images with " \
		"the same hash into a new directory", dest="dir", action="store_true")
	parser.add_argument("dirs", help="Directories to compare (default: " \
		"current directory)", nargs='*')
	args = parser.parse_args()
	if not args.dirs:
		args.dirs.append('.')

	clashes = findclash(args.dirs, args.fuzz, args.colored)

	#let's generate a list of the files that weren't the first
	if not sys.stdout.isatty():
		print('\n'.join(j for i in clashes.values() \
			if len(i) > 1 for j in list(i[args.all_clash:])))
		return

	for digest, loc in clashes.items():
		if len(loc) > 1:
			if args.dir and args.dirs == ['.']:
				target = os.path.join('.', digest)
				os.mkdir(target)
				for file in loc:
					os.rename(file, os.path.join(target, file))
			print("\x1b[31mSame file found:\x1b[m")
			print('\n'.join(loc), '\n')

if __name__ == "__main__":
	main()
