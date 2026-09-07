const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {spawn} = require('node:child_process');
const readline = require('node:readline');

async function startFixture(script) {
  // Signal Python directly; killing a uv wrapper can leave its child running.
  const child = spawn(path.resolve('.venv/bin/python'), [script],
    {stdio:['ignore','pipe','inherit']});
  const lines = readline.createInterface({input:child.stdout});
  const info = await new Promise((resolve,reject) => {
    const timer = setTimeout(()=>{child.kill('SIGTERM');reject(Error('Fixture startup timeout'))},30000);
    lines.once('line',line=>{clearTimeout(timer);lines.close();resolve(JSON.parse(line))});
    child.once('error',error=>{clearTimeout(timer);reject(error)});
    child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code))});
  });
  return {...info,child};
}

async function stopFixture(fixture) {
  const child = fixture.child;
  if(child.exitCode===null&&child.signalCode===null) {
    const exited = new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{child.kill('SIGKILL');reject(Error('Fixture cleanup timeout'))},10000);
      child.once('exit',code=>{clearTimeout(timer);code===0?resolve():reject(Error('Fixture cleanup exited '+code))});
    });
    child.kill('SIGTERM');
    await exited;
  }
  assert.ok(fixture.directory,'Fixture did not report its temporary directory');
  const removed=await fs.access(fixture.directory).then(()=>false,error=>{
    if(error.code==='ENOENT')return true;
    throw error;
  });
  assert.ok(removed,'Temporary fixture data was not removed: '+fixture.directory);
  return {status:'PASS',fixtureRemoved:true,productionDataWritten:false};
}

module.exports = {startFixture,stopFixture};
