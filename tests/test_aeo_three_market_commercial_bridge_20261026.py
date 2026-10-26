from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/"scripts/aeo_metro_gen.py"
TARGET={("general_contractor","NYC"),("hvac","DFW"),("roofing","DFW")}
CTA='<a class="btn btn-secondary" href="/commercial">Discuss a scoped market assessment</a>'

def current():
 s=spec_from_file_location("aeo_current_scoped",MOD)
 m=module_from_spec(s)
 s.loader.exec_module(m)
 return m

def previous(tmp_path):
 feature_change=subprocess.check_output([
     "git","-C",str(ROOT),"log","-1","--format=%H","--","scripts/aeo_metro_gen.py"
 ],text=True).strip()
 original=subprocess.check_output([
     "git","-C",str(ROOT),"show",
     feature_change+"^:scripts/aeo_metro_gen.py"
 ])
 q=tmp_path/"previous_generator.py"
 q.write_bytes(original)
 s=spec_from_file_location("aeo_previous_scoped",q)
 m=module_from_spec(s)
 s.loader.exec_module(m)
 return m

def test_exact_three_and_no_other_metro_page_changes(tmp_path):
 new=current()
 old=previous(tmp_path)
 assert len(new.NICHE_INFO)>=35
 assert len(new.METROS)==5
 changes=[]
 for niche in old.NICHE_INFO:
  for metro in old.METROS:
   past=old.generate_page(niche,metro)
   after=new.generate_page(niche,metro)
   if past!=after:
    changes.append((niche,metro))
    assert (niche,metro) in TARGET
    assert after.replace(CTA,"",1)==past
    assert after.count(CTA)==1
    assert after.count('href="/commercial"')==1
   else:
    assert (niche,metro) not in TARGET
 assert set(changes)==TARGET

def test_three_existing_real_aeo_pages_are_original_generator_source():
 old=current()
 for niche,metro in TARGET:
  live=Path("/srv/empire_os/runtime/aeo")/niche/metro/"index.html"
  content=live.read_text()
  assert content.count('<link rel="canonical"')==1
  # Before and after guarded website activation remain reproducible.
  assert content in (old.generate_page(niche,metro).replace(CTA,"",1),
                     old.generate_page(niche,metro))

def test_original_roofing_contextual_link_kept():
 candidate=current().generate_page("roofing","DFW")
 assert candidate.count('href="/industries/roofing"')==1
 assert candidate.count('href="/commercial"')==1
 assert 'qualified' in candidate
