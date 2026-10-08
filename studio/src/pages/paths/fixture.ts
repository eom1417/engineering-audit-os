// The gallery's and the unit tests' paths: the contract fixture (tests/fixtures/studio/v2/paths.json), mirrored here
// byte for byte so the Studio builds from its own folder; tests/test_studio_paths.py keeps the two equal.
import fixture from './fixture.json'
import type { PathsData } from './model'

export const PATHS_FIXTURE = fixture as unknown as PathsData
