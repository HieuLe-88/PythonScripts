import sys
from pydub import AudioSegment
from pydub.silence import split_on_silence

def trim_silence(input_file, output_file):
    # Load audio file
    sound = AudioSegment.from_file(input_file, format="wav")

    # Split audio based on silence, silence_threshold in dB
    silence_parts = split_on_silence(sound, min_silence_len=2000, silence_thresh=-50)

    # Combine non-silent parts into a single audio segment
    output_sound = AudioSegment.empty()
    for part in silence_parts:
        output_sound += part

    # Export trimmed audio to file
    output_sound.export(output_file, format="wav")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scriptname.py inputfilename")
        sys.exit(1)

    # Specify path to ffmpeg executable
    AudioSegment.converter = "C://Users//USER//Downloads//ffmpeg-7.0.1-full_build" 

    input_filename = sys.argv[1]
    output_filename = input_filename.replace(".wav", "_trimmed.wav")  # Output filename will be prefixed with "trimmed_"

    trim_silence(input_filename, output_filename)
    print("Trimmed audio saved to:", output_filename)
