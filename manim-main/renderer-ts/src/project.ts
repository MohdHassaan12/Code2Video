import {makeProject} from '@revideo/core';
import lesson from './lesson?scene';

export default makeProject({
  scenes: [lesson],
  variables: {input: null},
  settings: {shared: {size: {x: 1280, y: 720}}},
});
