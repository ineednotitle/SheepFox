/* ============================================================================
   (SheepFox) Zen browser — Windows setup launcher
   ----------------------------------------------------------------------------
   This is the source of `dist/SheepFox-Setup-<version>.exe`. The build script
   (mozbuild/scripts/build-installers.py) compiles it with Zig
   (`zig cc -target x86_64-windows-gnu`) and links in `payload.c`, which is the
   whole SheepFox payload as a byte array.

   The install preinstalls uBlock Origin + Decentraleyes through
   distribution\policies.json, so it asks for UAC like any other installer.
   -ProfileOnly keeps everything inside the profile.

   What it does at run time, in order:
     1. writes the embedded payload zip to %TEMP%\sheepfox-setup\
     2. expands it with PowerShell's Expand-Archive
     3. runs payload\scripts\install-windows.ps1 with whatever arguments the
        user passed, so  SheepFox-Setup.exe -System -LowMemory  works exactly
        like  .\scripts\install-windows.bat -System -LowMemory

   No registry writes, no services, no background processes: it is a launcher
   for the same script a git checkout would run, and it exits with the script's
   exit code.
   ============================================================================.
*/

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Generated at build time by build-installers.py. */
extern const unsigned char sheepfox_payload[];
extern const unsigned int sheepfox_payload_size;

#define SHEEPFOX_MAX_PATH_ 32768
#define SHEEPFOX_EXIT_FAIL 1

static void say(const char *text) {
  fputs(text, stdout);
  fputc('\n', stdout);
  fflush(stdout);
}

/* Run a command line through cmd.exe-free CreateProcessA and return its exit
   code, or -1 if it could not be started. */
static int run_and_wait(const char *command_line) {
  STARTUPINFOA si;
  PROCESS_INFORMATION pi;
  DWORD status = 0;

  ZeroMemory(&si, sizeof(si));
  si.cb = sizeof(si);
  ZeroMemory(&pi, sizeof(pi));

  /* CreateProcessA may modify the buffer, so hand it a copy. */
  {
    static char buffer[SHEEPFOX_MAX_PATH_ * 2];
    size_t length = strlen(command_line);
    if (length >= sizeof(buffer)) {
      return -1;
    }
    memcpy(buffer, command_line, length + 1);
    if (!CreateProcessA(NULL, buffer, NULL, NULL, TRUE, 0, NULL, NULL, &si, &pi)) {
      printf("Could not start:\n  %s\n  (error %lu)\n", command_line,
             (unsigned long)GetLastError());
      return -1;
    }
  }

  WaitForSingleObject(pi.hProcess, INFINITE);
  GetExitCodeProcess(pi.hProcess, &status);
  CloseHandle(pi.hProcess);
  CloseHandle(pi.hThread);
  return (int)status;
}

static int write_payload(const char *path) {
  HANDLE file;
  DWORD written = 0;

  file = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                     FILE_ATTRIBUTE_NORMAL, NULL);
  if (file == INVALID_HANDLE_VALUE) {
    return 0;
  }
  if (!WriteFile(file, sheepfox_payload, sheepfox_payload_size, &written, NULL)) {
    CloseHandle(file);
    return 0;
  }
  CloseHandle(file);
  return written == sheepfox_payload_size;
}

int main(int argc, char **argv) {
  char temp_root[SHEEPFOX_MAX_PATH_];
  char work_dir[SHEEPFOX_MAX_PATH_];
  char zip_path[SHEEPFOX_MAX_PATH_];
  char extract_dir[SHEEPFOX_MAX_PATH_];
  char script_path[SHEEPFOX_MAX_PATH_];
  char command[SHEEPFOX_MAX_PATH_ * 2];
  DWORD length;
  int index;
  int code;

  say("");
  say("  (SheepFox) Zen browser - Windows setup");
  say("  --------------------------------------");
  say("");

  for (index = 1; index < argc; ++index) {
    if (strcmp(argv[index], "/?") == 0 || strcmp(argv[index], "-h") == 0 ||
        strcmp(argv[index], "--help") == 0) {
      say("Usage: SheepFox-Setup.exe [installer switches]");
      say("");
      say("  -ProfileOnly  profile only: no extension preinstall, no admin needed");
      say("  -NoExtensions install the policy but preinstall nothing");
      say("  -System       install the policy + AutoConfig (default; asks for UAC)");
      say("  -Strict       add the strict anti-fingerprinting overrides");
      say("  -LowMemory    minimal-RAM profile (turns Fission isolation off)");
      say("  -NoUI         skip the floating-search theme");
      say("  -Doctor       diagnose an install, write nothing");
      say("  -Probe        write the CSS load probe, -Unprobe removes it");
      say("  -Report       write sheepfox-report.txt");
      say("  -Uninstall    remove everything SheepFox installed");
      say("  -DryRun       show what would happen, change nothing");
      say("");
      say("Every switch is forwarded to scripts\\install-windows.ps1.");
      return 0;
    }
  }

  length = GetTempPathA(SHEEPFOX_MAX_PATH_, temp_root);
  if (length == 0 || length >= SHEEPFOX_MAX_PATH_) {
    say("[error] could not resolve %TEMP%.");
    return SHEEPFOX_EXIT_FAIL;
  }
  wsprintfA(work_dir, "%ssheepfox-setup", temp_root);
  wsprintfA(zip_path, "%spayload.zip", work_dir);
  wsprintfA(extract_dir, "%spayload", work_dir);
  wsprintfA(script_path, "%s\\scripts\\install-windows.ps1", extract_dir);

  CreateDirectoryA(work_dir, NULL);

  printf("  unpacking %u bytes to %s\n", sheepfox_payload_size, work_dir);
  if (!write_payload(zip_path)) {
    say("[error] could not write the payload to %TEMP%.");
    return SHEEPFOX_EXIT_FAIL;
  }

  wsprintfA(command,
            "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "
            "\"$ErrorActionPreference='Stop'; Expand-Archive -LiteralPath '%s' "
            "-DestinationPath '%s' -Force\"",
            zip_path, extract_dir);
  if (run_and_wait(command) != 0) {
    say("[error] could not unpack the payload (PowerShell Expand-Archive).");
    return SHEEPFOX_EXIT_FAIL;
  }

  {
    char quoted[SHEEPFOX_MAX_PATH_ * 2];
    /* Forward the caller's switches unchanged. */
    wsprintfA(quoted,
              "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"%s\"",
              script_path);
    for (index = 1; index < argc; ++index) {
      strncat(quoted, " ", sizeof(quoted) - strlen(quoted) - 1);
      strncat(quoted, argv[index], sizeof(quoted) - strlen(quoted) - 1);
    }
    say("");
    code = run_and_wait(quoted);
  }

  if (code == 0) {
    say("");
    say("  Done. Restart Zen Browser (or Firefox) to activate SheepFox.");
  } else {
    printf("\n  Installer exited with code %d.\n", code);
  }
  return code;
}
