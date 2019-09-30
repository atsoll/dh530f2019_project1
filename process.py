import os
import csv
import string
from itertools import islice

#some nltk things
from nltk.corpus import stopwords
import nltk
from nltk.tokenize import word_tokenize

#Yes this global set up isn't great practice but this is mosly spaghetti code as it is...
#To clean up if ever actually used

# import and set up the stanford pos tagger (so it'll work on french...)
from nltk.tag import StanfordPOSTagger
jar = './resources/postagger/stanford-postagger-3.9.2.jar'
fr_model = './resources/postagger/models/french.tagger'
fr_tagger = StanfordPOSTagger(fr_model, jar, encoding='utf8' )

#global vars
vowels = 'aeiouyéèàêùëï'
ipa_vowels = 'iyuwIYoʊeɛɝθaɔəɑæɔ̃ɑ̃ɥ'
punc_table = str.maketrans('', '', '!?,."«»():;')
en_stop = set(stopwords.words('english'))


#pronunciation dictionaries for syllable counts/rhyming
fr_dict = {}
with open('./resources/fr.csv', newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    for row in reader:
        try:
            fr_dict[row[0]] = row[1].replace(" ","")
        except Exception:
            continue

en_dict = {}
with open('./resources/cmudict.ipa', newline='', encoding='utf-8') as f:
    for line in f.readlines():
        l = line.split('\t')
        en_dict[l[0]] = l[1].replace(" ","").rstrip()

#for csv writers
fields = ["song", "fr_w", "en_w", "fr_s", "en_s", "more_en", "more_fr", "spw_en", "spw_fr", "wpl_en", "wpl_fr", "spl_en", "spl_fr", "lines"]
pos_fields = ["song", '*', 'Adjectives', 'Verbs', 'Prepositions', 'Nouns', 'Adverbs', 'Conjunctions', 'Pronouns']
rhyme_fields = ["song","abab_fr", "abab_en", "abba_fr", "abba_en", "run_fr", "run_en", "distinct_fr", "distinct_en"]

csv_res = open("results.csv", 'w', newline='')
writer = csv.DictWriter(csv_res, fieldnames=fields)

pos_csv_en = open("pos_en.csv", 'w', newline='')
pos_csv_fr = open("pos_fr.csv", 'w', newline='')
pos_en_writer = csv.DictWriter(pos_csv_en, fieldnames=pos_fields)
pos_fr_writer = csv.DictWriter(pos_csv_fr, fieldnames=pos_fields)

rhyme_csv = open("rhymes.csv",'w',newline="")
rhyme_writer = csv.DictWriter(rhyme_csv, fieldnames=rhyme_fields)

writer.writeheader()
rhyme_writer.writeheader()
pos_en_writer.writeheader()
pos_fr_writer.writeheader()



def main():
    for folder in os.listdir('./songs'):
      #create the results file
      res_file = open('./songs/' + folder + '/results.txt', 'w')
      #get prepped
      #choosing to work with arrays of lines so that I dont't have to constantly open the files
      fr = open('./songs/' + folder + '/fr.txt', 'r')
      fr_text = fr.readlines()
      en = open('./songs/' + folder + '/en.txt', 'r')
      en_text = en.readlines()
      translation = open('./songs/' + folder + '/translation.txt', 'r')
      translation_text = translation.readlines()
      en.close()
      fr.close()
      translation.close()
      #do the actual processing
      counts = countThings(fr_text, en_text)
      countReport(counts, len(en_text), res_file)
      en_pos, fr_pos = posTag(en_text, 'en'), posTag(fr_text, 'fr')
      posReport(en_pos, fr_pos, res_file, folder)
      rhymeReport(rhymeScheme(fr_text, fr_dict),rhymeScheme(en_text, en_dict), res_file, folder)
      similarityReport(en_text, translation_text, res_file)
      d_res= {"song":folder}
      d_res.update(counts)
      writer.writerow(d_res)
      #do the thing properly and remember to close the file
      res_file.close()
    csv_res.close()

#for counting words/sylls for both, num differences, which way they swung
def countThings(french, english):
    res = {"fr_w":0, "en_w":0, "fr_s":0, "en_s":0, "more_en":0, "more_fr":0}
    #use split for tokenization because I don't want to count contractions as separate words (because they're not being pronounced as such)
    #use looping rather than list comp to avoid duplication of splitting
    lines = len(english)
    res["lines"] = lines
    for i in range(len(english)):
        fr_words = french[i].lower().split()
        en_words = english[i].lower().split()
        res["fr_w"] += len(fr_words)
        res["en_w"] += len(en_words)
        e_s = sum([syllables(x) for x in en_words ])
        f_s = sum([syllables_fr(x) for x in fr_words ])
        if(e_s!=f_s):
            if(e_s>f_s):
                res['more_en'] +=1
            else:
                res['more_fr'] += 1
        res["en_s"]+= e_s
        res["fr_s"]+= f_s
    res["wpl_en"] = res["en_w"]/lines
    res["wpl_fr"] = res["fr_w"]/lines
    res["spl_en"] = res["en_s"]/lines
    res["spl_fr"] = res["fr_s"]/lines
    res["spw_en"] = res["en_s"]/res["en_w"]
    res["spw_fr"] = res["fr_s"]/res["fr_w"]
    res["more_en"]/=lines
    res["more_fr"]/=lines

    return res

def countReport(stats, num_lines, file):
    output = "{}:\n\twords:{}\n\tavg words per line:{}\n\tsyllables:{}\n\tavg syllables per line:{}\n\tavg syllables per word:{}\n\n"
    file.write(output.format("English", stats["en_w"], stats["en_w"]/num_lines, stats["en_s"], stats["en_s"]/num_lines, stats["en_s"]/stats["en_w"]))
    file.write(output.format("French", stats["fr_w"], stats["fr_w"]/num_lines, stats["fr_s"], stats["fr_s"]/num_lines, stats["fr_s"]/stats["fr_w"]))
    file.write("Lines with more english syllables: {}\n".format(stats["more_en"]))
    file.write("Lines with more french syllables: {}\n\n".format(stats["more_fr"]))


#adjusted from https://datascience.stackexchange.com/questions/23376/how-to-get-the-number-of-syllables-in-a-word
#evidently there are some language issues but it seems to work for the most part
#example of bad: "somehow"

def syllables(word):
    count = 0
    if word[0] in vowels:
        count +=1
    for index in range(1,len(word)):
        if word[index] in vowels and word[index-1] not in vowels:
            count +=1
    if word.endswith('e'):
        count -= 1
    if word.endswith('le'):
        count+=1
    if count == 0:
        count +=1
    return count

#deals with the edge case of words ending in 'bre', 'cre', 'dre' etc.
def syllables_fr(word):
    s = syllables(word)
    if(word.endswith('re') and (word[len(word)-3] not in vowels)) :
        s+=1
    return s

#english tagset: https://www.clips.uantwerpen.be/pages/mbsp-tags (penn treebank)
#french tagset: http://www.linguist.univ-paris-diderot.fr/~mcandito/Publications/crabbecandi-taln2008-final.pdf (adapted from french treebank)
def mapPos(pos):
    if(pos.startswith("ADJ") or pos.startswith('JJ')):
        return "Adjectives"
    elif(pos.startswith('V')):
        return "Verbs"
    elif(pos.startswith('N')):
        return "Nouns"
    elif(pos.startswith('PR')):
        return "Pronouns"
    elif(pos=='CC' or pos=='CS'):
        return 'Conjunctions'
    elif(('RB' in pos) or pos.startswith('ADV')):
        return "Adverbs"
    elif(pos=='P' or pos=='IN'):
        return "Prepositions"
    #catch all for fine grained tags or things we don't care about
    return "*"

def posTag(text, lang):
    res_dict = {}
    for line in text:
        words = nltk.pos_tag(word_tokenize(line.translate(punc_table))) if lang=='en' else fr_tagger.tag(line.translate(punc_table).split())
        for w in words:
            pos = mapPos(w[1])
            if(res_dict.get(pos)):
                res_dict[pos] +=1
            else:
                res_dict[pos] = 1
    return res_dict

def mapDict(f,d):
    for k, v in list(d.items()):
        d[k] = f(v)

#keeping the unidentified ones is important for graphs
def posReport(en_dict, fr_dict, file, song):
    fr_words = sum(list(fr_dict.values()))
    en_words = sum(list(en_dict.values()))

    mapDict(lambda x: x/fr_words, fr_dict)
    mapDict(lambda x: x/en_words, en_dict)

    file.write("English: {}\n".format(en_dict))
    file.write("French: {}\n".format(fr_dict))

    en_dict["song"] = song
    pos_en_writer.writerow(en_dict)
    fr_dict["song"] = song
    pos_fr_writer.writerow(fr_dict)


#for testing document similarity of vocab
#onehot + shared vocab
def similarityReport(en, tr, file):
    en_oh = onehot(en)
    tr_oh = onehot(tr)
    shared = [x for x in en_oh.keys() if x in tr_oh.keys()]
    file.write("Top words in the original: {}\n".format( sorted(en_oh.items(), key=lambda kv: kv[1], reverse=True)[:10]))
    file.write("Top words in the translation: {}\n".format( sorted(tr_oh.items(), key=lambda kv: kv[1], reverse=True)[:10]))
    file.write("Distinct shared non stopwords: {}\n\n".format(len(shared)))
    file.write("Vocab shared with the original: {}%".format((len(shared)/len(en_oh))*100))

def onehot(text):
    vector = {}
    for line in text:
        for word in line.translate(punc_table).lower().split():
            if word not in en_stop:
                if(vector.get(word)):
                    vector[word] +=1
                else:
                    vector[word] = 1
    return vector

#create a rhyme scheme string
def rhymeScheme(lines, lang_dict):
    ends = [y[len(y)-1] for y in [x.replace("-", " ").replace("’", " ").replace("'", " ").translate(punc_table).split() for x in lines]]
    sounds = {}
    labels = ""
    letter = 64
    for l in ends:
        try:
            phon = lang_dict[l.lower()]
        except KeyError:
            phon =  None
        if(phon):
            match = None
            key = None
            for l in list(sounds.keys()):
                match = soundMatch(phon, sounds[l])
                if(match):
                    break
            if(match):
                sounds[l] = match
                labels += l
            else:
                letter += 1
                #skip over non letters to lowercase
                if letter == 91:
                    letter = 97
                labels += chr(letter)
                sounds[chr(letter)] = phon
        else:
            labels+="*"
    label_dict = {}
    for c in labels:
        if label_dict.get(c):
            label_dict[c]+=1
        else:
            label_dict[c] = 1

    return [labels, sounds, sorted(label_dict.items(), key=lambda kv: kv[1], reverse=True)]

def schemeCounter(scheme_str):
    abba_count = 0
    abab_count = 0
    runs = []

    i=0
    while(i< len(scheme_str)-3):
      if(scheme_str[i]==scheme_str[i+3] and scheme_str[i+1]==scheme_str[i+2] and scheme_str[i+1]!=scheme_str[i]):
        abba_count +=1
        i += 4
      elif(scheme_str[i]==scheme_str[i+2] and scheme_str[i+1]==scheme_str[i+3] and scheme_str[i+1]!=scheme_str[i]):
        abab_count+=1
        i+= 4
      else:
        i+=1

    run = 1
    for y in range(len(scheme_str)):
        if(y==len(scheme_str)-1 or scheme_str[y]!=scheme_str[y+1]):
            runs.append(run)
            run =1
        else:
            run +=1
    return [abba_count, abab_count, max(runs)]

def rhymeReport(fr_data, en_data, file, song):
    file.write("\nFrench scheme:{}\nEnglish scheme:{}\n".format(fr_data[0], en_data[0]))
    file.write("French sounds:{}\nEnglish sounds:{}\n\n".format(fr_data[1], en_data[1]))
    file.write("French occurences:{}\nEnglish occurences:{}\n\n".format(fr_data[2], en_data[2]))
    en_counts = schemeCounter(en_data[0])
    fr_counts = schemeCounter(fr_data[0])
    rhyme_writer.writerow({"song":song,"abab_fr":fr_counts[1], "abab_en":en_counts[1], "abba_fr":fr_counts[0], "abba_en":en_counts[0], "run_fr":fr_counts[2], "run_en":en_counts[2], "distinct_fr":len(fr_data[1].keys()), "distinct_en":len(en_data[1])})

#finds the longest rhyming fragment
#a rhyme must include at minimum a vowel
#semi vowels make it a bit iffy
def soundMatch(phon1, phon2):
    count = 0
    has_vowel = False
    for x in range(min(len(phon1), len(phon2))):
        if(phon1[len(phon1)-1-x]==phon2[len(phon2)-1-x]):
            count +=1
            if(phon1[len(phon1)-1-x] in ipa_vowels):
                has_vowel = True
        else:
            break
    if(has_vowel and count > 0):
        return phon1[(-1*count):]
    return None


main()
